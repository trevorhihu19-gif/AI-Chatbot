import json 
from datetime import datetime, timezone, timedelta
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, transaction
from app.core.security import get_current_user, verify_clerk_webhook
from app.models.user import User
from app.models.usage import UsageCredit

logger = structlog.get_logger(__name__)
router = APIRouter()

PLAN_TOKEN_LIMITS = {
    "free": 100_000,
    "pro": 1_000_000,
    "enterprise": 10_000_000,
}

@router.post("/webhooks/clerk", status_code=200, include_in_schema=False)
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    svix_id: str = Header(None, alias="svix-id"),
    svix_timestamp: str = Header(None, alias="svix-timestamp"),
    svix_signature: str = Header(None, alias="svix-signature")
):
    payload = await request.body()

    if not verify_clerk_webhook(payload, svix_id, svix_timestamp, svix_signature):
        logger.warning("webhook.Invalid_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )
    event = json.loads(payload)
    event_type: str = event.get("type", "")
    data: dict = event.get("data", {})

    logger.info("webhook.received", event_type=event_type)

    if event_type == "user.created":
        await _create_user(db, data)
    elif event_type == "user.updated":
        await _update_user(db, data)
    elif event_type == "user.deleted":
        await _delete_user(db, data)
    else:
        logger.debug("webhook.unhandled", event_type=event_type)
    return {"status": "ok"}


async def _create_user(db: AsyncSession, data: dict) -> None:
    clerk_id = data.get("id")

    emails = data.get("email_addresses", [])
    primary_id = data.get("primary_email_address_id")
    email = ""

    for e in emails:
        if e.get("id") == primary_id:
            email = e.get("email_address", "")
            break
    
    if not email:
        logger.error("webhook.user_created.no_email", clerk_id=clerk_id)
        return
    
    async with transaction(db):
        existing = await db.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        if existing.scalar_one_or_none():
            logger.info("webhook.user_already_exists", clerk_id=clerk_id)
            return
        
        user = User(
            clerk_id=clerk_id,
            email=email,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            avatar_url=data.get("image_url"),
            plan_tier="free",
        )
        db.add(user)
        await db.flush()

        usage = UsageCredit(
            user_id=user.id,
            tokens_used=0,
            tokens_limit=PLAN_TOKEN_LIMITS["free"],
            reset_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(usage)

    logger.info("webhook.user_created", clerk_id=clerk_id, email=email)

async def _update_user(db: AsyncSession, data: dict) -> None:
    clerk_id = data.get("id")

    result = await db.execute(
        select(User).where(User.clerk_id == clerk_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning("webhook.user_not_found", clerk_id=clerk_id)
        return
    
    async with transaction(db):
        emails = data.get("email_addresses", [])
        primary_id = data.get("primary_email_address_id")
        for e in emails:
            if e.get("id") == primary_id:
                user.email = e.get("email_address", user.email)
                break

        user.first_name = data.get("first_name", user.first_name)
        user.last_name = data.get("last_name", user.last_name)
        user.avatar_url = data.get("image_url", user.avatar_url)

    logger.info("webhook.user_updated", clerk_id=clerk_id)

async def _delete_user(db: AsyncSession, data: dict) -> None:
    clerk_id = data.get("id")

    result = await db.execute(
        select(User).where(User.clerk_id == clerk_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        return

    async with transaction(db):
        user.is_active = False

    logger.info("webhook.user_deleted", clerk_id=clerk_id)

@router.get("/users/me")
async def get_me(
    current_user: User = Depends(get_current_user)
): 
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "avatar_url": current_user.avatar_url,
        "plan_tier": current_user.plan_tier,
        "created_at": current_user.created_at.isoformat(),
    }

@router.get("/users/me/usage")
async def get_my_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UsageCredit).where(UsageCredit.user_id == current_user.id)
    )
    usage = result.scalar_one_or_none()

    if not usage:
        async with transaction(db):
            usage = UsageCredit(
                user_id=current_user.id,
                tokens_used=0,
                tokens_limit=PLAN_TOKEN_LIMITS.get(current_user.plan_tier, 100_000),
                reset_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.add(usage)
    return {
        "tokens_used": usage.tokens_used,
        "tokens_limit": usage.tokens_limit,
        "tokens_remaining": usage.tokens_remaining,
        "usage_percentage": usage.usage_percentage,
        "reset_at": usage.reset_at.isoformat() if usage.reset_at else None,
    }