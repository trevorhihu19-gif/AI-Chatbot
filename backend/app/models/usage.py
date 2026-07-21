import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User

class UsageCredit(Base):
    __tablename__ = "usage_credits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )

    tokens_used: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    tokens_limit: Mapped[int] = mapped_column(
        BigInteger, 
        default=100_000,
        nullable=False
    )

    reset_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="usage")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_usage_credits_user"),
        Index("ix_usage_reset_at", "reset_at"),
        {}
    )

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.tokens_limit - self.tokens_used)
    
    @property
    def usage_percentage(self) -> float:
        if self.tokens_limit == 0:
            return 100.0
        return round((self.tokens_used / self.tokens_limit) * 100, 1)
    
    @property
    def is_exhausted(self) -> bool:
        return self.tokens_used >= self.tokens_limit
    
    def __repr__(self) -> str:
        return f"<UsageCredit used={self.tokens_used}/{self.tokens_limit}>"