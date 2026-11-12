"""Local inference settings, bounded in-process admission, and Ollama metadata."""
import asyncio
from dataclasses import dataclass
from fastapi import HTTPException
from app.core.config import settings

PRESETS = {
    "balanced": {"temperature": 0.7, "top_p": 0.9},
    "creative": {"temperature": 1.1, "top_p": 0.95},
    "precise": {"temperature": 0.25, "top_p": 0.75},
    "roleplay": {"temperature": 0.85, "top_p": 0.92},
    "custom": {"temperature": 0.7, "top_p": 0.9},
}

@dataclass(frozen=True)
class InferenceOptions:
    model: str
    temperature: float
    top_p: float
    num_ctx: int
    num_predict: int


def effective_options(character, conversation=None):
    preset = getattr(conversation, "generation_preset", "balanced") or "balanced"
    defaults = PRESETS.get(preset, PRESETS["balanced"])
    model = (getattr(conversation, "inference_model", None) or
             getattr(character, "preferred_model", None) or settings.ollama_model)
    return InferenceOptions(
        model=model,
        temperature=(getattr(conversation, "temperature", None) if getattr(conversation, "temperature", None) is not None else defaults["temperature"]),
        top_p=(getattr(conversation, "top_p", None) if getattr(conversation, "top_p", None) is not None else defaults["top_p"]),
        num_ctx=getattr(conversation, "context_window", None) or 4096,
        num_predict=getattr(conversation, "response_length", None) or 384,
    )

class LocalInferenceQueue:
    """Single-process cap. Not a distributed queue; use a shared coordinator when scaling."""
    def __init__(self, capacity=2, wait_seconds=20):
        self.capacity = capacity
        self.wait_seconds = wait_seconds
        self._semaphore = asyncio.Semaphore(capacity)
        self.running = 0
        self.waiting = 0

    async def acquire(self):
        self.waiting += 1
        try:
            try:
                await asyncio.wait_for(self._semaphore.acquire(), timeout=self.wait_seconds)
            except asyncio.TimeoutError as exc:
                raise HTTPException(503, "Local inference capacity busy; retry shortly") from exc
            self.running += 1
        finally:
            self.waiting -= 1

    def release(self):
        self.running -= 1
        self._semaphore.release()

    def snapshot(self):
        return {"running": self.running, "waiting": self.waiting, "capacity": self.capacity,
                "scope": "per-api-process", "wait_timeout_seconds": self.wait_seconds}

queue = LocalInferenceQueue(settings.inference_concurrency, settings.inference_wait_seconds)


def new_inference_admission():
    """One permit per response stream (distributed when Redis configured)."""
    if settings.redis_url:
        from app.services.distributed_inference import create_distributed_queue
        return create_distributed_queue()
    if settings.environment == "production":
        raise RuntimeError("Production inference requires REDIS_URL")
    # Share the existing local semaphore across all requests.
    return queue

async def release_inference_admission(admission):
    import inspect
    result = admission.release()
    if inspect.isawaitable(result):
        await result

async def inference_snapshot():
    if settings.redis_url:
        from app.services.distributed_inference import create_distributed_queue
        return await create_distributed_queue().snapshot()
    return queue.snapshot()


def validate_resource_limits(options):
    """Reject excessive context requests instead of silently exhausting VRAM."""
    if options.num_ctx > settings.inference_max_context:
        raise HTTPException(422, f"Context exceeds server limit of {settings.inference_max_context} tokens")
    if options.num_predict > settings.inference_max_output:
        raise HTTPException(422, f"Output exceeds server limit of {settings.inference_max_output} tokens")
    if options.num_ctx < options.num_predict + 128:
        raise HTTPException(422, "Context window must accommodate output tokens and system headroom")
