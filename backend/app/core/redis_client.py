"""
SmartHire AI — Redis Client

Provides:
- Async Redis connection (aioredis via redis-py v5)
- Cache get/set/delete helpers with TTL support
- JSON serialization/deserialization for cached objects
- Health check
"""

import json
from typing import Any, Optional

import structlog
from redis.asyncio import Redis, from_url

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ── Module-level client (initialized on startup) ──────────────────────────────
_redis_client: Optional[Redis] = None


async def init_redis() -> None:
    """Initialize the Redis connection. Called on application startup."""
    global _redis_client
    try:
        _redis_client = await from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        await _redis_client.ping()
        logger.info("Redis connection established", url=settings.REDIS_URL)
    except Exception as e:
        logger.error("Redis connection failed", error=str(e))
        raise


async def close_redis() -> None:
    """Close the Redis connection. Called on application shutdown."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis connection closed")


def get_redis() -> Redis:
    """Return the active Redis client. Raises RuntimeError if not initialized."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis_client


# ── Cache Helpers ─────────────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    """
    Retrieve a value from Redis cache.

    Returns the deserialized Python object, or None if key does not exist.
    """
    try:
        client = get_redis()
        raw = await client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning("Cache get failed", key=key, error=str(e))
        return None


async def cache_set(
    key: str,
    value: Any,
    ttl: int = settings.CACHE_TTL_SECONDS,
) -> bool:
    """
    Store a value in Redis cache with TTL (seconds).

    Args:
        key: Cache key.
        value: Any JSON-serializable Python object.
        ttl: Time-to-live in seconds (default: 300 = 5 minutes).

    Returns:
        True on success, False on failure.
    """
    try:
        client = get_redis()
        serialized = json.dumps(value, default=str)
        await client.setex(key, ttl, serialized)
        return True
    except Exception as e:
        logger.warning("Cache set failed", key=key, error=str(e))
        return False


async def cache_delete(key: str) -> bool:
    """Delete a key from Redis cache."""
    try:
        client = get_redis()
        await client.delete(key)
        return True
    except Exception as e:
        logger.warning("Cache delete failed", key=key, error=str(e))
        return False


async def cache_delete_pattern(pattern: str) -> int:
    """
    Delete all keys matching a pattern (e.g., 'cache:dashboard:*').

    Returns the number of keys deleted.
    """
    try:
        client = get_redis()
        keys = await client.keys(pattern)
        if keys:
            return await client.delete(*keys)
        return 0
    except Exception as e:
        logger.warning("Cache pattern delete failed", pattern=pattern, error=str(e))
        return 0


# ── Token Storage (Refresh Tokens) ───────────────────────────────────────────

async def store_refresh_token(user_id: str, token: str) -> None:
    """Store a refresh token in Redis with 7-day TTL."""
    key = f"auth:refresh:{user_id}"
    ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    await cache_set(key, token, ttl=ttl)


async def get_refresh_token(user_id: str) -> Optional[str]:
    """Retrieve the stored refresh token for a user."""
    key = f"auth:refresh:{user_id}"
    return await cache_get(key)


async def revoke_refresh_token(user_id: str) -> None:
    """Invalidate a user's refresh token (logout)."""
    key = f"auth:refresh:{user_id}"
    await cache_delete(key)


# ── Health Check ──────────────────────────────────────────────────────────────

async def get_redis_status() -> bool:
    """Ping Redis. Returns True if reachable."""
    try:
        client = get_redis()
        result = await client.ping()
        return result is True
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        return False
