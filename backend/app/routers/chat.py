import json
import uuid
import tiktoken
from typing import AsyncGenerator, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, transaction, AsyncSessionLocal
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
tokenizer = tiktoken.get_encoding("cl100k_base")
router = APIRouter(prefix="/chat", tags=["chat"])

MAX_HISTORY = 10

PLAN_TOKEN_LIMITS = {
    "free": 100_000,
    "pro": 1_000_000,
    "enterprise": 10_000_000,
}

def _count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(tokenizer.encode(text))

async def _get_or_create_conversation(
        db: AsyncSession,
        user: User,
        conversation_id: Optional[uuid.UUID],
        first_message: str
) -> Conversation:
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
    messages = list(reversed(result.scalars().all()))

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
    clean_message = sanitize_text(request_body.message)

    # Check usage limits
    usage_result = await db.execute(
        select(UsageCredit).where(UsageCredit.user_id == current_user.id)
    )
    usage = usage_result.scalar_one_or_none()

    # Ensure every user has a usage record matching their tier limits explicitly
    if usage is None:
        usage = UsageCredit(
            user_id=current_user.id,
            tokens_limit=PLAN_TOKEN_LIMITS.get(getattr(current_user, "plan_tier", "free"), 100_000)
        )
        db.add(usage)
        await db.commit()
        await db.refresh(usage)

    if usage and usage.tokens_used >= usage.tokens_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Monthly token limit reached. Please upgrade your plan."
        )
    
    conversation = await _get_or_create_conversation(
        db=db,
        user=current_user,
        conversation_id=request_body.conversation_id,
        first_message=clean_message
    )

    history = await _load_history(db, conversation.id)

    # Save user message to database
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

    return StreamingResponse(
        _generate_sse_stream(
            message=clean_message,
            history=history,
            user=current_user,
            conversation_id=conversation.id,
            use_rag=request_body.use_rag,
            use_web_search=request_body.use_web_search,
            session_factory=AsyncSessionLocal,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )

async def _generate_sse_stream(
    message: str,
    history: list,
    user: User,
    conversation_id,
    use_rag: bool,
    use_web_search: bool,
    session_factory,
) -> AsyncGenerator[str, None]:
    full_response = ""
    final_citations = []
    stream_completed = False

    # Calculate input prompt token weight context upfront
    history_text = " ".join([m.content for m in history if hasattr(m, 'content')])
    prompt_tokens = _count_tokens(message + " " + history_text)

    try:
        async with session_factory() as db:
            conversation = await db.get(Conversation, conversation_id)
            if conversation is None:
                raise RuntimeError("Conversation not found")

            yield _sse(
                type="metadata",
                conversation_id=str(conversation.id),
            )

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
                    yield _sse(type="token", content=content)

                elif chunk_type == "tool_start":
                    yield _sse(
                        type="tool_start",
                        tool_name=chunk.get("tool_name")
                    )
            
                elif chunk_type == "done":
                    final_citations.extend(chunk.get("citations", []))
                    stream_completed = True

                elif chunk_type == "error":
                    error_msg = chunk.get("error", "Unknown error")
                    logger.error("chat.stream.agent_error", error=error_msg)
                    yield _sse(type="error", error=error_msg)
                    return 
                
            if not stream_completed:
                logger.warning(
                    "chat.stream.incomplete",
                    conversation_id=str(conversation.id),
                )
                return

            # Compute output token metric and calculate complete cost
            completion_tokens = _count_tokens(full_response)
            total_tokens_spent = prompt_tokens + completion_tokens

            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=full_response,
                completion_tokens=completion_tokens,
                tool_call_data=json.dumps(
                    {"citations": final_citations}
                ) if final_citations else None,
            )
            db.add(assistant_message)

            # Update credit metrics safely via row locking
            await _update_usage(db, user.id, total_tokens_spent)

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
                tokens=total_tokens_spent,
                citations=len(final_citations)
            )

            yield _sse(
                type="done",
                message_id=str(assistant_message.id),
                citations=final_citations
            )

    except Exception as e:
        logger.error("chat.stream.error", error=str(e))
        yield _sse(type="error", error="Something went wrong. Please try again")

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
    
    await db.delete(conv)
    await db.commit()
    
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