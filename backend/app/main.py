import uuid
import os
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.security import limiter
from app.routers import health, users

logger = structlog.get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        "surge.starting",
        version=settings.app_version,
        environment=settings.app_env
    )

    await init_db()

    os.makedirs(settings.upload_dir, exist_ok=True)
    logger.info("surge.ready")
    yield

    logger.info("surge.shutting_down")
    await close_db()
    logger.info("surge.stopped")

def create_app() -> FastAPI:
    app = FastAPI(
        title="Surge",
        version=settings.app_version,
        description="Production-grade AI chatbot with RAG and hybrid search",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600
    )

    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(SlowAPIMiddleware)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
    
    register_error_handlers(app)

    API_PREFIX = "/api/v1"

    app.include_router(health.router)
    app.include_router(users.router, prefix=API_PREFIX)

    logger.info(
        "surge.routes_registered",
        count=len(app.routes)
    )
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

    