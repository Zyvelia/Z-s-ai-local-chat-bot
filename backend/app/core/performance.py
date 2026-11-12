"""Low-cardinality aggregate performance counters, not per-user telemetry.

No request body, token, email, address, chat content or arbitrary URL path is
stored. Exposed only through the existing admin dependency.
"""
import time
from fastapi import Request
from app.core.redis_runtime import get_redis

async def performance_middleware(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        await _record('error', time.perf_counter() - start)
        raise
    await _record('ok' if response.status_code < 400 else 'error', time.perf_counter() - start)
    return response

async def _record(kind, seconds):
    redis = get_redis()
    if redis is None:
        return
    try:
        pipe = redis.pipeline(transaction=True)
        # Aggregate buckets; avoid high-cardinality paths and identifiers.
        pipe.hincrby('cc:metrics:api', f'{kind}_requests', 1)
        pipe.hincrby('cc:metrics:api', 'duration_ms_sum', round(seconds * 1000))
        if seconds >= 2:
            pipe.hincrby('cc:metrics:api', 'slow_over_2s', 1)
        await pipe.execute()
    except Exception:
        return  # monitoring must not interrupt requests
