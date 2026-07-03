import structlog
import asyncio
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import check_db_health

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    try:
        db_health = await asyncio.wait_for(
            check_db_health(),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
        db_health = {
            "status": "unhealthy",
            "message": "Database health check timed out",
        }

    all_healthy = db_health["status"] == "healthy"

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "version": settings.app_version,
            "environment": settings.app_env,
            "dependencies": {
                "database": db_health
            }
        }
    )

@router.get("/ping")
async def ping():
    return {"pong": True}