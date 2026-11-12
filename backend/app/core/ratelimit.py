"""Shared Redis rate limits; no X-Forwarded-For trust without an edge proxy."""
import hashlib
import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.redis_runtime import get_redis

_lock = Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)
MAX_KEYS = 20000

# One atomic fixed-window operation. The key contains only a hashed client ID.
LIMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1])) end
return {count, redis.call('TTL', KEYS[1])}
"""

def rules(method: str, path: str) -> tuple[int, int] | None:
    if method not in {'POST', 'PUT', 'PATCH', 'DELETE'}: return None
    if path.endswith('/auth/login') or path.endswith('/auth/register'): return (10, 60)
    if path.endswith('/messages/stream') or path.endswith('/messages/regenerate') or path.endswith('/group/turn') or path.endswith('/characters/preview'): return (12, 60)
    if path.endswith('/reports') or path.endswith('/appeals'): return (5, 3600)
    return (90, 60)

def hit(key: str, limit: int, window: int, now: float | None = None) -> tuple[bool, int]:
    """Local-only fallback for explicitly non-Redis development instances."""
    t = time.monotonic() if now is None else now
    with _lock:
        if key not in _hits and len(_hits) >= MAX_KEYS:
            _hits.pop(next(iter(_hits)))
        values = _hits[key]
        while values and values[0] <= t - window: values.popleft()
        if len(values) >= limit:
            return False, max(1, int(values[0] + window - t) + 1)
        values.append(t)
        return True, 0

async def redis_hit(key: str, limit: int, window: int, client=None) -> tuple[bool, int]:
    conn = client or get_redis()
    if conn is None:
        raise RuntimeError('Redis rate limiting requested without Redis')
    digest = hashlib.sha256(key.encode('utf8')).hexdigest()
    count, ttl = await conn.eval(LIMIT, 1, f'cc:rl:{digest}', window)
    return int(count) <= limit, max(1, int(ttl)) if count > limit else 0

async def rate_limit_middleware(request: Request, call_next):
    rule = rules(request.method, request.url.path)
    if rule is not None:
        ip = request.client.host if request.client else 'unknown'
        key = f'{ip}:{request.method}:{request.url.path.rsplit("/", 1)[0]}'
        try:
            if settings.redis_url:
                allowed, retry = await redis_hit(key, *rule)
            else:
                if settings.environment == 'production':
                    return JSONResponse(status_code=503, content={'detail': 'Shared rate limiting required'})
                allowed, retry = hit(key, *rule)
        except Exception:
            return JSONResponse(status_code=503, content={'detail': 'Rate limiting temporarily unavailable'})
        if not allowed:
            return JSONResponse(status_code=429, content={'detail': 'Too many requests'}, headers={'Retry-After': str(retry)})
    return await call_next(request)
