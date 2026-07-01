import logging
import sys
from typing import Any
import sentry_sdk
import structlog
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from app.core.config import settings

def setup_logging() -> None:
    _setup_structlog()
    _setup_sentry()

def _setup_structlog() -> None:
    shared_processors: list[Any] = [
        # Merges any context variables bound earlier in the request
        structlog.contextvars.merge_contextvars,

        # Adds "level": "info" / "error" etc.
        structlog.stdlib.add_log_level,

        # Adds "logger": "app.core.database" etc.
        structlog.stdlib.add_logger_name,

        # Adds "timestamp"
        structlog.processors.TimeStamper(fmt="iso"),

        # If an exception was passed, formats the traceback
        structlog.processors.format_exc_info,
    ]

    if settings.debug:
        # Development: coloured, indented, human-readable
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Production: one JSON object per line
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        # Sets the minimum log level based on environment
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        # Cache the logger after first use — performance optimisation
        cache_logger_on_first_use=True,
    )

    # Also configure Python's built-in logging to flow through structlog
    # This captures logs from SQLAlchemy, httpx, and other libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.debug else logging.INFO,
    )

    # Silence noisy libraries we don't care about
    for noisy_logger in ["httpx", "httpcore", "asyncio", "multipart"]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

def _setup_sentry() -> None:
    if not settings.sentry_dsn:
        # No DSN configured — skip Sentry entirely
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=f"surge@{settings.app_version}",

        # Sample rate for performance tracing
        # 0.2 = capture 20% of requests as traces (to manage Sentry quota)
        traces_sample_rate=0.2,

        integrations=[
            # Automatically captures FastAPI request context on errors
            FastApiIntegration(transaction_style="endpoint"),

            # Captures SQLAlchemy queries in Sentry breadcrumbs
            SqlalchemyIntegration(),

            # Captures WARNING+ logs as Sentry breadcrumbs
            # Captures ERROR+ logs as full Sentry events
            LoggingIntegration(
                level=logging.WARNING,
                event_level=logging.ERROR,
            ),
        ],
        # Don't send personally identifiable information
        send_default_pii=False,
    )

def capture_exception(exc: Exception, context: dict | None = None) -> None:
    if context:
        with sentry_sdk.push_scope() as scope:
            for key, value in context.items():
                scope.set_extra(key, value)
            sentry_sdk.capture_exception(exc)
    else:
        sentry_sdk.capture_exception(exc)
