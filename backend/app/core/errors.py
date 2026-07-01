import traceback
from typing import Any
import sentry_sdk
import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.config import settings

logger = structlog.get_logger(__name__)

def make_error_response(
        code: str,
        message: str,
        status_code: int,
        details: Any = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details and settings.debug:
        body["error"]["details"] = details

    return JSONResponse(status_code=status_code, content=body)

async def http_exception_handler(
        request: Request, exc: HTTPException
) -> JSONResponse:
    logger.warning(
        "http.exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
    )
    return make_error_response(
        code=status_code_to_string(exc.status_code),
        message=str(exc.detail),
        status_code=exc.status_code
    )

async def validation_exception_handler(
        request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for err in exc.errors():
        errors.append({
            "field": "->".join(str(x) for x in err["loc"]),
            "message": err["msg"],
        })

    logger.warning(
        "validation.error",
        path=request.url.path,
        errors=errors
    )
    return make_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=errors
    )

async def integrity_error_handler(
        request: Request, exc: IntegrityError
) -> JSONResponse:
    logger.error(
        "db.integrity.error",
        path=request.url.path,
        error=str(exc.orig)
    )
    orig = str(exc.orig).lower()
    if "unique" in orig:
        message = "A record with this details already exists"
    elif "foreign key" in orig:
        message = "Referenced resource not found"
    elif "not null" in orig:
        message = "A required field is missing"
    else:
        message = "Database constraint violation"

    return make_error_response(
        code="CONFLICT",
        message=message,
        status_code=status.HTTP_409_CONFLICT,
    )

async def operational_error_handler(
        request: Request, exc: OperationalError
) -> JSONResponse:
    logger.error(
        "db.operational.error",
        path=request.url.path,
        error=str(exc)
    )
    sentry_sdk.capture_exception(exc)
    return make_error_response(
        code="DATABASE_ERROR",
        message="Database temporarily available.Please try again.",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE
    )

async def generic_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    tb = traceback.format_exc()
    logger.error(
        "unhandled.exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        traceback=tb
    )
    sentry_sdk.capture_exception(exc)
    return make_error_response(
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.Our team has been notified.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=tb
    )

def status_code_to_string(code: int) ->str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(code, f"HTTP_{code}")

def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(IntegrityError, integrity_error_handler)
    app.add_exception_handler(OperationalError, operational_error_handler)
    app.add_exception_handler(Exception, generic_exception_handler)