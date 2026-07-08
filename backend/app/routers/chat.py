import json
import uuid
from typing import AsyncGenerator, Optional
import structlog
from fastapi import APIRouter ,Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, transaction
from app.core.security import get_current_user, sanitize_text
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.usage import UsageCredit
from app.models.user import User
from app.schemas.chat import (
    ChatRequest, 
    ConversationDetail,
    ConversationOut,
    MessageOut
)
from app.services.agent import run_agent_streaming
from app.core.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

MAX_HISTORY = 10

async def _get_or_create_conversation(
        db: AsyncSession,
        user: User,
        conversation_id: Optional[uuid.UUID],
        first_message: str
) -> Conversation:
    """
    Load an existing conversation or create a new one.
    Auto-generates a title from the first message.
    """
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        return conv
    
    title = first_message[:60] + ("..." if len(first_message) > 60 else "")

    conv = Conversation(
        user_id=user.id,
        title=title,
        model_used=settings.groq_model
    )
    db.add(conv)
    await db.flush()
    return conv

async def _load_history(
        db: AsyncSession,
        conversation_id: uuid.UUID
) -> list:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .where(Message.role.in_(["user", "assistant"]))
        .order_by(desc(Message.created_at))
        .limit(MAX_HISTORY)
    )
    messages = result.scalars().all()

    history = []
    for msg in messages:
        if msg.role == "user":
            history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            history.append(AIMessage(content=msg.content))
    return history

async def _update_usage(
        db: AsyncSession,
        user_id: uuid.UUID,
        tokens: int
) -> None:
    result = await db.execute(
        select(UsageCredit)
        .where(UsageCredit.user_id == user_id)
        .with_for_update()
    )
    usage = result.scalar_one_or_none()
    if usage:
        usage.tokens_used += tokens
        await db.flush()

@router.post("/stream")
async def stream_chat(
    request_body: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    #sanitize text
    clean_message = sanitize_text(request_body.message)

    #Check usage limits
    usage_result = await db.execute(
        select(UsageCredit).where(UsageCredit.user_id == current_user.id)
    )
    usage = usage_result.scalar_one_or_none()
    if usage and usage.is_exhausted:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Monthly token limit reached.Please upgrade your plan."
        )
    
    #load or create new conversation
    conversation = await _get_or_create_conversation(
        db=db,
        user=current_user,
        conversation_id=request_body.conversation_id,
        first_message=clean_message
    )

    #load chat history
    history = await _load_history(db, conversation.id)

    #save the user's messages to the database
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=clean_message
    )
    db.add(user_message)
    await db.commit()

    logger.info(
        "chat.stream.starting",
        user_id=str(current_user.id),
        conversation_id=str(conversation.id),
        use_rag=request_body.use_rag,
        use_web_search=request_body.use_web_search
    )

    #Build and return the Server-Sent Events(SSE)
    return StreamingResponse(
        _generate_sse_stream(
            message=clean_message,
            history=history,
            user=current_user,
            conversation=conversation,
            use_rag=request_body.use_rag,
            use_web_search=request_body.use_web_search,
            db=db
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "connection": "keep-alive",
        }
    )

async def _generate_sse_stream(
        message: str,
        history: list,
        user: User,
        conversation: Conversation,
        use_rag: bool,
        use_web_search: bool,
        db: AsyncSession
) -> AsyncGenerator[str, None]:
    """
    Async generator that runs the agent and yields SSE-formatted strings.

    SSE format:
        data: <json>\n\n

    The double newline is the SSE event separator — required by the protocol.
    Without it, the client won't know where one event ends and the next begins.
    """
    full_response = ""
    final_citations = []
    total_tokens = 0

    yield _sse(
        type="metadata",
        conversation_id=str(conversation.id)
    )

    try:
        async for chunk in run_agent_streaming(
            message=message,
            history=history,
            user_id=str(user.id),
            conversation_id=str(conversation.id),
            use_rag=use_rag,
            use_web_search=use_web_search
        ):
            chunk_type = chunk.get("type")

            if chunk_type == "token":
                content = chunk.get("content", "")
                full_response += content
                total_tokens += len(content)
                yield _sse(type="token", content=content)

            elif chunk_type == "tool_start":
                yield _sse(
                    type="tool_start",
                    tool_name=chunk.get("tool_name")
                )
            
            elif chunk_type == "done":
                final_citations.extend(chunk.get("citations", []))

                assistant_message = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_response,
                    completion_tokens=total_tokens,
                    citations=json.dumps(final_citations) if final_citations else None,
                )
                db.add(assistant_message)

                await _update_usage(db, user.id, total_tokens)

                tools_used = []
                if use_rag:
                    tools_used.append("rag")
                if use_web_search:
                    tools_used.append("web_search")
                conversation.tools_used = json.dumps(tools_used)

                await db.commit()

                logger.info(
                    "chat.stream.complete",
                    conversation_id=str(conversation.id),
                    tokens=total_tokens,
                    citations=len(final_citations)
                )

                yield _sse(
                    type="done",
                    message_id=str(assistant_message.id),
                    citations=final_citations
                )

            elif chunk_type == "error":
                error_msg = chunk.get("error", "Unknown error")
                logger.error("chat.stream.agent_error", error=error_msg)
                yield _sse(type="error", error=error_msg)

    except Exception as e:
        logger.error("chat.stream.error", error=str(e))
        await db.rollback()
        yield _sse(type="error", error="Something went wrong.Please try again")

def _sse(**kwargs) -> str:
    return f"data: {json.dumps(kwargs)}\n\n"

@router.get("/conversations", response_model=list[ConversationOut])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    archived: bool = False,
):
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id == current_user.id,
            Conversation.is_archived == archived,
        )
        .order_by(
            desc(Conversation.is_pinned),
            desc(Conversation.updated_at),
        )
    )
    conversations = result.scalars().all()
    return conversations

@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at)
    )
    messages = msg_result.scalars().all()

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        is_pinned=conv.is_pinned,
        is_archived=conv.is_archived,
        model_used=conv.model_used,
        messages=[MessageOut.model_validate(m) for m in messages],
        updated_at=conv.updated_at,
    )

@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    async with transaction(db):
        await db.delete(conv)
    
    logger.info(
        "conversation.deleted",
        conversation_id=str(conversation_id),
        user_id=str(current_user.id),
    )

@router.patch("/conversations/{conversation_id}/pin", status_code=200)
async def toggle_pin(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    async with transaction(db):
        conv.is_pinned = not conv.is_pinned
    return {"id": str(conv.id), "is_pinned": conv.is_pinned}

   


