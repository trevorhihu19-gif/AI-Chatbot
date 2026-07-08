from contextlib import asynccontextmanager
from typing import AsyncGenerator
import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from datetime import datetime
import time
from sqlalchemy import text

from app.core.config import settings

logger = structlog.get_logger(__name__)

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=settings.debug
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)

class Base(DeclarativeBase):
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except SQLAlchemyError as exc:
            await session.rollback()
            logger.error("db.rollback", error=str(exc))
            raise
        except Exception as exc:
            await session.rollback()
            logger.error("db.unexpected_rollback", error=str(exc))
            raise
        finally:
            await session.close()

@asynccontextmanager
async def transaction(session: AsyncSession):
    async with session.begin():
        try:
            yield session
        except Exception as exc:
            logger.error("transaction.rollback", error=str(exc))
            raise

async def check_db_health() -> dict:
    start = time.monotonic()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        logger.error("db.health_check.failed", error=str(exc))
        return {"status": "unhealthy", "error": str(exc)}
    
async def init_db() -> None:
    health = await check_db_health()
    if health["status"] != "healthy":
        raise RuntimeError(f"Database unreachable: {health}")
    logger.info("db.connected", latency_ms=health["latency_ms"])


async def close_db() -> None:
    await engine.dispose()
    logger.info("db.pool.disposed")
