"""FIFO Redis-backed inference admission with expiring renewable leases.

Every worker shares the same Redis sorted sets. This is distributed admission
control, *not* a durable task queue: network streams still execute on the
requesting API worker. Work is cancelled when the caller disconnects.
"""
import asyncio
import time
import uuid
from fastapi import HTTPException
from app.core.redis_runtime import get_redis
from app.core.config import settings

# KEYS: active, waiting. ARGV: request_id, wall_time, capacity, lease_secs,
# queue_limit. Only the oldest waiter may claim a free slot. The token is
# random per request, never derived from a user ID.
ACQUIRE = """
local active, waiting = KEYS[1], KEYS[2]
local token, now = ARGV[1], tonumber(ARGV[2])
local capacity, ttl, max_waiters = tonumber(ARGV[3]), tonumber(ARGV[4]), tonumber(ARGV[5])
redis.call('ZREMRANGEBYSCORE', active, '-inf', now)
redis.call('ZREMRANGEBYSCORE', waiting, '-inf', now - ttl)
local position = redis.call('ZRANK', waiting, token)
if not position and redis.call('ZCARD', waiting) >= max_waiters then return -1 end
if not position then redis.call('ZADD', waiting, now, token) end
local first = redis.call('ZRANGE', waiting, 0, 0)[1]
if first == token and redis.call('ZCARD', active) < capacity then
  redis.call('ZREM', waiting, token)
  redis.call('ZADD', active, now + ttl, token)
  redis.call('EXPIRE', active, ttl * 2)
  redis.call('EXPIRE', waiting, ttl * 2)
  return 1
end
redis.call('EXPIRE', waiting, ttl * 2)
return 0
"""
RENEW = """
if redis.call('ZSCORE', KEYS[1], ARGV[1]) then
  redis.call('ZADD', KEYS[1], tonumber(ARGV[2]) + tonumber(ARGV[3]), ARGV[1])
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]) * 2)
  return 1
end
return 0
"""
CLEANUP = """
redis.call('ZREM', KEYS[1], ARGV[1]); redis.call('ZREM', KEYS[2], ARGV[1]); return 1
"""

class DistributedInferenceQueue:
    def __init__(self, capacity=2, wait_seconds=20, lease_seconds=120, max_waiters=100,
                 namespace='cc:inference', redis_provider=get_redis):
        if capacity < 1 or wait_seconds <= 0 or lease_seconds < 10 or max_waiters < 1:
            raise ValueError('Invalid inference admission limits')
        self.capacity, self.wait_seconds, self.lease_seconds = capacity, wait_seconds, lease_seconds
        self.max_waiters = max_waiters
        self.active, self.waiting = f'{namespace}:active', f'{namespace}:waiting'
        self.redis_provider = redis_provider
        self.token = None
        self._heartbeat = None
        self.running = 0
        self.lease_lost = False
        self.waiting_local = 0

    def _redis(self):
        conn = self.redis_provider()
        if conn is None:
            raise RuntimeError('REDIS_URL required for distributed admission')
        return conn

    async def acquire(self):
        # One instance per stream; never share a mutable token across requests.
        if self.token is not None:
            raise RuntimeError('Admission permit already held')
        token = uuid.uuid4().hex
        conn = self._redis()
        deadline = time.monotonic() + self.wait_seconds
        self.waiting_local += 1
        try:
            while True:
                try:
                    result = await conn.eval(ACQUIRE, 2, self.active, self.waiting,
                        token, time.time(), self.capacity, self.lease_seconds, self.max_waiters)
                except Exception as exc:
                    raise HTTPException(503, 'Inference coordination unavailable') from exc
                if result == 1:
                    self.token = token
                    self.running = 1
                    self.lease_lost = False
                    self._heartbeat = asyncio.create_task(self._renew(token))
                    return
                if result == -1:
                    raise HTTPException(503, 'Inference waiting queue full')
                if time.monotonic() >= deadline:
                    raise HTTPException(503, 'Inference waiting queue timeout')
                await asyncio.sleep(min(.25, max(0, deadline - time.monotonic())))
        finally:
            self.waiting_local -= 1
            if self.token != token:
                # A cancelled/timed-out waiter must not block the FIFO.
                try:
                    await conn.eval(CLEANUP, 2, self.active, self.waiting, token)
                except Exception:
                    pass  # expired waiter entry will be swept on next admission

    async def _renew(self, token):
        try:
            while True:
                await asyncio.sleep(max(1, self.lease_seconds // 3))
                renewed = await self._redis().eval(RENEW, 1, self.active, token,
                                                    time.time(), self.lease_seconds)
                if renewed != 1:
                    self.lease_lost = True
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            self.lease_lost = True
            # Fail closed mid-generation: caller stops on next token.
            return

    async def release(self):
        token, heartbeat = self.token, self._heartbeat
        self.token, self._heartbeat, self.running = None, None, 0
        if heartbeat:
            heartbeat.cancel()
            try:
                await heartbeat
            except asyncio.CancelledError:
                pass
        if token:
            try:
                await self._redis().eval(CLEANUP, 2, self.active, self.waiting, token)
            except Exception:
                pass  # time-bound lease provides eventual release

    async def snapshot(self):
        try:
            conn = self._redis()
            counts = await conn.pipeline().zcard(self.active).zcard(self.waiting).execute()
            return {'running': counts[0], 'waiting': counts[1], 'capacity': self.capacity,
                    'scope': 'redis-distributed', 'wait_timeout_seconds': self.wait_seconds}
        except Exception:
            return {'running': None, 'waiting': None, 'capacity': self.capacity,
                    'scope': 'redis-distributed', 'status': 'unavailable'}


def create_distributed_queue():
    return DistributedInferenceQueue(
        capacity=settings.inference_concurrency,
        wait_seconds=settings.inference_wait_seconds,
        lease_seconds=settings.inference_lease_seconds,
        max_waiters=settings.inference_max_waiters)
