import uuid
from datetime import datetime
from typing import  Optional
from pydantic import BaseModel, Field, field_validator

class ChatRequest(BaseModel):
    conversation_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Omit to start a new conversation"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=32_000,
    )

    use_web_search: bool = False
    use_rag: bool = True

    @field_validator("message")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()
    
class StreamChunk(BaseModel):
    type: str
    content: Optional[str] = None
    tool_name: Optional[str] = None
    citations: Optional[list[dict]] = None
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    error: Optional[str] = None

class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str
    is_pinned: bool
    is_archived: bool
    model_used: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}

class MessageOut(BaseModel):
    id:uuid.UUID
    role: str
    content: str
    tool_name: Optional[str] = None
    citations: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class ConversationDetail(BaseModel):
    id: uuid.UUID
    title: str
    is_pinned: bool
    is_archived: bool
    model_used: Optional[str] = None
    messages: list[MessageOut] = []
    updated_at: datetime

    model_config = {"from_attributes": True}