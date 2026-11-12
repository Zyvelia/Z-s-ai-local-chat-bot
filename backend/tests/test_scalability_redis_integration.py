"""Optional genuine Redis/Lua tests; run in CI when TEST_REDIS_URL is set."""
import os
import uuid
import pytest
from app.core.ratelimit import redis_hit
from app.services.distributed_inference import DistributedInferenceQueue

@pytest.mark.asyncio
async def test_real_redis_admission_and_rate_limit():
    if not os.environ.get('TEST_REDIS_URL'):
        pytest.skip('Set TEST_REDIS_URL for real Redis evaluation')
    from redis.asyncio import Redis
    redis = Redis.from_url(os.environ['TEST_REDIS_URL'], decode_responses=True)
    namespace = 'cc:test:' + uuid.uuid4().hex
    a = DistributedInferenceQueue(capacity=1, wait_seconds=.05, lease_seconds=30,
                                  namespace=namespace, redis_provider=lambda: redis)
    b = DistributedInferenceQueue(capacity=1, wait_seconds=.05, lease_seconds=30,
                                  namespace=namespace, redis_provider=lambda: redis)
    try:
        await a.acquire()
        assert (await a.snapshot())['running'] == 1
        with pytest.raises(Exception):
            await b.acquire()
        await a.release()
        await b.acquire()
        await b.release()
        key = namespace + ':limit'
        assert (await redis_hit(key, 1, 60, client=redis))[0] is True
        assert (await redis_hit(key, 1, 60, client=redis))[0] is False
    finally:
        await a.release()
        await b.release()
        await redis.delete(a.active, a.waiting)
        await redis.aclose()
