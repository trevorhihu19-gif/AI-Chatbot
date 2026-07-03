import re
from typing import Annotated, Optional
import bleach
import httpx
import structlog
import hmac
import hashlib
import base64
import time
from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

logger = structlog.get_logger(__name__)

limiter = Limiter(key_func=get_remote_address)

#CLERK JWT VERIFICATION
_jwks_cache: Optional[dict] = None
_jwks_cache_updated_at: float = 0.0
JWKS_CACHE_TTL = 3600  

async def _get_clerk_public_keys(force_refresh: bool = False) -> dict:
    global _jwks_cache, _jwks_cache_updated_at
    now = time.time()
    has_valid_cache =  (
        _jwks_cache is not None
        and (now - _jwks_cache_updated_at) < JWKS_CACHE_TTL
    )

    if has_valid_cache and not force_refresh:
        return _jwks_cache

    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.clerk.com/v1/jwks",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            timeout=10.0
        )
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache

def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid format. Expected:Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return token

async def verify_clerk_token(token: str) -> dict:
    try:
        jwks = await _get_clerk_public_keys()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                public_key = key
                break
        
        if not public_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signing key not found"
            )
        
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"verify_aud": False}
        )
        return payload
    except JWTError as exc:
        logger.warning("jwt.invalid", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except httpx.HTTPError as exc:
        logger.error("clerk.jwks.failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable"
        )
    
#ARCJET PROTECTION
async def arcject_protect(
    request: Request,
    user_id: Optional[str] = None,
) -> None:
    if not settings.arcjet_key:
        return

    client_ip = request.client.host if request.client else "unknown"

    payload = {
        "sdkStack": "PYTHON",
        "sdkVersion": "1.0.0",
        "fingerprint": {
            "ip": client_ip,
            "userId": user_id,
        },
        "rules": [
            {
                "type": "RATE_LIMIT",
                "mode": "LIVE",
                "characteristics": ["userId"] if user_id else ["ip"],
                "window": "60s",
                "max": 60,
            },
            {
                "type": "BOT",
                "mode": "LIVE",
                "allow": ["VERIFIED_BOT"],
            },
            {
                "type": "SHIELD",
                "mode": "LIVE",
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                "https://decide.arcjet.com/v1/decide",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.arcjet_key}",
                    "Content-Type": "application/json",
                },
            )

        decision = response.json()
        verdict = decision.get("conclusion")

        if verdict == "ALLOW":
            return

        elif verdict == "DENY":
            reason = decision.get("reason", {})

            if reason.get("isRateLimit"):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please slow down.",
                    headers={"Retry-After": "60"},
                )

            if reason.get("isBot"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Automated requests are not allowed",
                )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request blocked by security policy",
            )

        elif verdict == "CHALLENGE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Additional verification required.",
            )

        elif verdict == "ERROR":
            logger.warning(
                "arcjet.error_response",
                client_ip=client_ip,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Security service temporarily unavailable.",
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Invalid security service response.",
            )

    except HTTPException:
        raise

    except Exception as exc:
        logger.error(
            "arcjet.failed",
            error=str(exc),
            client_ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Security verification failed.",
        )

#AUTH DEPENDENCY
async def get_current_user(
        request: Request,
        authorization: Annotated[Optional[str], Header()] = None,
        db: AsyncSession = Depends(get_db)
) -> User:
    token = _extract_bearer_token(authorization)
    claims = await verify_clerk_token(token)

    clerk_id: str = claims.get("sub", "")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim"
        )
    
    await arcject_protect(request, user_id=clerk_id)

    result = await db.execute(
        select(User).where(User.clerk_id == clerk_id)
    )
    user = result.scalar_one_or_none()

    hashed_clerk_id = hashlib.sha256(clerk_id.encode()).hexdigest()[:12]

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.Please sign in again."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.Contact support"
        )
    
    logger.info("auth.success", user=hashed_clerk_id)
    return user

#INPUT SANITIZATION
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+a",
    r"pretend\s+(you\s+are|to\s+be)",
    r"disregard\s+(your\s+)?instructions",
    r"system\s*:\s*you",
    r"<\|im_start\|>",
    r"\[INST\]",
]
_INJECTION_REGEX = re.compile(
    "|".join(_INJECTION_PATTERNS),
    re.IGNORECASE | re.DOTALL,
)

MAX_MESSAGE_LENGTH = 32_000  # 8k tokens

def sanitize_text(text: str) -> str:
    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Message cannot be empty"
        )
    
    clean = bleach.clean(text, tags=[], attributes={}, strip=True)
    clean = re.sub(r"\s{3,}", "\n\n", clean).strip()

    if len(clean) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Message too long.Maximum {MAX_MESSAGE_LENGTH} characters"
        )
    
    if _INJECTION_REGEX.search(clean):
        logger.warning("security.prompt_injection", preview=clean[:100])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message contains disallowed patterns"
        )
    return clean

def sanitize_filename(filename: str) -> str:
    name = filename.replace("/", "_").replace("\\", "_").replace("..", "_")
    name = re.sub(r"[^\w\-.]", "_", name)
    if not name or name in {".", ".."}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid filename",
        )
    return name

WEBHOOK_TIMESTAMP_TOLERANCE = 300

def verify_clerk_webhook(
    payload: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
) -> bool:
    try:
        timestamp = int(svix_timestamp)
    except (TypeError, ValueError):
        return False

    now = int(time.time())

    if abs(now - timestamp) > WEBHOOK_TIMESTAMP_TOLERANCE:
        return False

    signed_content = f"{svix_id}.{svix_timestamp}.{payload.decode()}"

    secret = base64.b64decode(
        settings.clerk_webhook_secret.replace("whsec_", "")
    )

    expected = hmac.new(
        secret,
        signed_content.encode(),
        hashlib.sha256,
    ).digest()

    expected_b64 = base64.b64encode(expected).decode()

    for sig in svix_signature.split(" "):
        _, _, sig_value = sig.partition(",")
        if hmac.compare_digest(expected_b64, sig_value):
            return True

    return False
    




    

   
    
