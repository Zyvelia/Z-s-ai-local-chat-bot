"""Shared Redis connection. Redis is optional ONLY in single-process local development.

Do not configure REDIS_URL in production unless Redis is reachable: callers fail
closed for admission and rate limits instead of silently falling back.
"""
from functools import lru_cache
from app.core.config import settings

@lru_cache(maxsize=1)
def get_redis():
    if not settings.redis_url:
        return None
    from redis.asyncio import Redis  # optional for Redis-disabled dev/test environments
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=3, health_check_interval=30)

async def close_redis():
    conn = get_redis()
    if conn is not None:
        await conn.aclose()
    get_redis.cache_clear()
