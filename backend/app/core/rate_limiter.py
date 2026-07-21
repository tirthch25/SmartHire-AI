"""
SmartHire AI — Rate Limiting Configuration

Uses SlowAPI (Starlette/FastAPI adapter for limits library).
Backed by Redis for distributed rate limiting across multiple workers.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# ── Limiter Instance ──────────────────────────────────────────────────────────
# key_func: use client IP address as the rate limit key.
# storage_uri: Redis backend so limits are shared across all API workers.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)

# ── Exported Limit Decorators ─────────────────────────────────────────────────
# Use these as decorators on route handlers:
#   @router.post("/login")
#   @rate_limit_auth
#   async def login(request: Request, ...):

# Import these in route files to apply targeted limits:
RATE_LIMIT_AUTH = settings.RATE_LIMIT_AUTH      # "10/minute" — auth endpoints
RATE_LIMIT_UPLOAD = settings.RATE_LIMIT_UPLOAD  # "5/minute"  — file upload
RATE_LIMIT_DEFAULT = settings.RATE_LIMIT_DEFAULT # "60/minute" — everything else
