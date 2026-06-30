import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Index, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.document import Document
    from app.models.usage import UsageCredit

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    clerk_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True,
        index=True,
    )

    first_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    plan_tier: Mapped[str] = mapped_column(
        String(32),
        default="free",
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    documents: Mapped[Optional["Document"]] = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    usage: Mapped[Optional["UsageCredit"]] = relationship(
        "UsageCredit",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_users_plan_active", "plan_tier", "is_active"), {}
    )

    def __repr__(self) -> str:
        return f"<User clerk_id={self.clerk_id!r} email={self.email!r}"
