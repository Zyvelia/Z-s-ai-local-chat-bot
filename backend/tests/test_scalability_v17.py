"""v1.7 source-level tests using isolated Redis test doubles.
Live Redis/Lua execution is separately exercised in CI via Redis service.
"""
import asyncio
import hashlib
import re
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app.services.distributed_inference import DistributedInferenceQueue, ACQUIRE, RENEW, CLEANUP
from app.core.ratelimit import redis_hit, rules
from app.services.inference import new_inference_admission, LocalInferenceQueue
from app.core.config import settings
from app.models.entities import Base


class ScriptedRedis:
    """Logic-level fake for atomic Lua commands, not a substitute for real Redis."""
    def __init__(self):
        self.active = {}
        self.waiting = {}
        self.keys = []
        self.limits = defaultdict(int)

    async def eval(self, script, count, *argv):
        if script == ACQUIRE:
            active, waiting, token, now, capacity, ttl, max_waiters = argv
            now, capacity, ttl, max_waiters = float(now), int(capacity), int(ttl), int(max_waiters)
            self.active = {k:v for k,v in self.active.items() if v > now}
            self.waiting = {k:v for k,v in self.waiting.items() if v > now-ttl}
            if token not in self.waiting and len(self.waiting) >= max_waiters:
                return -1
            self.waiting.setdefault(token, now)
            if min(self.waiting, key=self.waiting.get) == token and len(self.active) < capacity:
                self.waiting.pop(token)
                self.active[token] = now+ttl
                return 1
            return 0
        if script == CLEANUP:
            _, _, token = argv
            self.waiting.pop(token, None)
            self.active.pop(token, None)
            return 1
        if script == RENEW:
            _, token, now, ttl = argv
            if token in self.active:
                self.active[token] = float(now)+int(ttl)
                return 1
            return 0
        # Redis rate-limit Lua script: fixed window counter.
        key, window = argv
        self.keys.append(key)
        self.limits[key] += 1
        return [self.limits[key], int(window)]

    def pipeline(self):
        return FakePipeline(self)

class FakePipeline:
    def __init__(self, parent):
        self.parent = parent
        self.query = []
    def zcard(self, name):
        self.query.append(name)
        return self
    async def execute(self):
        return [len(self.parent.active if key.endswith(':active') else self.parent.waiting) for key in self.query]


@pytest.mark.asyncio
async def test_distributed_admission_is_shared_across_instances():
    redis = ScriptedRedis()
    a = DistributedInferenceQueue(capacity=1, wait_seconds=.05, lease_seconds=30, redis_provider=lambda:redis)
    b = DistributedInferenceQueue(capacity=1, wait_seconds=.05, lease_seconds=30, redis_provider=lambda:redis)
    await a.acquire()
    try:
        with pytest.raises(HTTPException) as exc:
            await b.acquire()
        assert exc.value.status_code == 503
        assert len(redis.active) == 1
        assert not redis.waiting
        assert (await a.snapshot())['running'] == 1
    finally:
        await a.release()
    await b.acquire()
    await b.release()
    assert not redis.active


@pytest.mark.asyncio
async def test_distributed_queue_caps_waiters_and_cleans_cancellations():
    redis = ScriptedRedis()
    a = DistributedInferenceQueue(capacity=1, wait_seconds=1, lease_seconds=30, max_waiters=1, redis_provider=lambda:redis)
    b = DistributedInferenceQueue(capacity=1, wait_seconds=1, lease_seconds=30, max_waiters=1, redis_provider=lambda:redis)
    c = DistributedInferenceQueue(capacity=1, wait_seconds=1, lease_seconds=30, max_waiters=1, redis_provider=lambda:redis)
    await a.acquire()
    pending = asyncio.create_task(b.acquire())
    try:
        await asyncio.sleep(.02)
        with pytest.raises(HTTPException, match='queue full'):
            await c.acquire()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert not redis.waiting
    finally:
        await a.release()


@pytest.mark.asyncio
async def test_lost_lease_flag_and_renewal():
    redis = ScriptedRedis()
    a = DistributedInferenceQueue(capacity=1, wait_seconds=.1, lease_seconds=12, redis_provider=lambda:redis)
    await a.acquire()
    token = a.token
    assert await redis.eval(RENEW, 1, a.active, token, time.time(), 12) == 1
    assert redis.active[token] > time.time()
    await a.release()
    assert await redis.eval(RENEW, 1, a.active, token, time.time(), 12) == 0


@pytest.mark.asyncio
async def test_shared_rate_limit_hashes_client_identity():
    redis = ScriptedRedis()
    for _ in range(2):
        assert (await redis_hit('10.0.0.1:POST:auth', 2, 60, client=redis))[0]
    allowed, retry = await redis_hit('10.0.0.1:POST:auth', 2, 60, client=redis)
    assert not allowed and retry == 60
    assert all('10.0.0.1' not in key for key in redis.keys)
    assert redis.keys[0] == 'cc:rl:' + hashlib.sha256('10.0.0.1:POST:auth'.encode()).hexdigest()
    assert (await redis_hit('10.0.0.2:POST:auth', 2, 60, client=redis))[0]


def test_settings_and_migration_are_consistent(monkeypatch):
    assert settings.database_pool_size > 0
    assert '013_performance_indexes.sql' in [p.name for p in Path(__file__).parents[1].joinpath('migrations').glob('*.sql')]
    sql = Path(__file__).parents[1].joinpath('migrations/013_performance_indexes.sql').read_text()
    for table in ('conversations', 'messages', 'learned_memories', 'story_events', 'characters'):
        assert f' ON {table} ' in sql
        assert table in Base.metadata.tables
    monkeypatch.setattr(settings, 'redis_url', '')
    monkeypatch.setattr(settings, 'environment', 'development')
    assert isinstance(new_inference_admission(), LocalInferenceQueue)


def test_lua_and_rate_rules_contract():
    assert "ZREMRANGEBYSCORE" in ACQUIRE
    assert "ZADD" in ACQUIRE and "ZRANK" in ACQUIRE
    assert "EXPIRE" in RENEW and "ZREM" in CLEANUP
    assert rules('POST', '/api/v1/auth/login') == (10, 60)
    assert rules('GET', '/api/v1/characters') is None


def test_resource_safeguards_reject_large_requests(monkeypatch):
    from app.services.inference import validate_resource_limits
    monkeypatch.setattr(settings, 'inference_max_context', 4096)
    monkeypatch.setattr(settings, 'inference_max_output', 512)
    validate_resource_limits(SimpleNamespace(num_ctx=2048, num_predict=256))
    with pytest.raises(HTTPException) as err:
        validate_resource_limits(SimpleNamespace(num_ctx=8192, num_predict=256))
    assert err.value.status_code == 422
    with pytest.raises(HTTPException):
        validate_resource_limits(SimpleNamespace(num_ctx=2048, num_predict=1024))
    with pytest.raises(HTTPException):
        validate_resource_limits(SimpleNamespace(num_ctx=512, num_predict=448))


@pytest.mark.asyncio
async def test_ollama_only_public_model_metadata_is_cached(monkeypatch):
    import httpx
    from app.providers.ollama import OllamaProvider
    class Cache:
        def __init__(self): self.values = {}
        async def get(self, key): return self.values.get(key)
        async def set(self, key, value, ex):
            assert ex <= 60
            self.values[key] = value
    cache = Cache()
    monkeypatch.setattr('app.providers.ollama.get_redis', lambda: cache)
    real_client = httpx.AsyncClient
    requests = []
    def handler(req):
        requests.append(req.url.path)
        return httpx.Response(200, json={'models': [{'name': 'local:latest', 'size': 999}]})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda *a, **k: real_client(*a, transport=httpx.MockTransport(handler), **k))
    provider = OllamaProvider()
    first = await provider.models()
    second = await provider.models()
    assert first == second
    assert requests == ['/api/tags']
    assert 'cc:cache:ollama:installed_models' in cache.values
    assert not any('prompt' in k or 'conversation' in k for k in cache.values)
