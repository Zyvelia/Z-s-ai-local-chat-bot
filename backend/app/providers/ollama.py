"""Self-hosted Ollama HTTP adapter. No external cloud AI dependency."""
import json
from app.core.redis_runtime import get_redis
import httpx
from collections.abc import AsyncIterator
from app.providers.base import ChatProvider
from app.core.config import settings

class OllamaProvider(ChatProvider):
    @property
    def base(self):
        return settings.ollama_base_url.rstrip("/")

    async def models(self):
        # Only public Ollama installation metadata is cached. No prompts, user
        # records, characters, memory or private conversation text are cached.
        conn = get_redis()
        key = "cc:cache:ollama:installed_models"
        if conn is not None:
            try:
                cached = await conn.get(key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base}/api/tags")
            response.raise_for_status()
            models = [{"name": m["name"], "size": m.get("size"),
                       "modified_at": m.get("modified_at"), "details": m.get("details", {})}
                      for m in response.json().get("models", []) if isinstance(m.get("name"), str)]
        if conn is not None:
            try:
                await conn.set(key, json.dumps(models), ex=max(1, min(settings.ollama_cache_ttl_seconds, 60)))
            except Exception:
                pass
        return models

    async def ensure_installed(self, model: str):
        names = {m["name"] for m in await self.models()}
        if model not in names:
            raise ValueError("Selected model is not installed on Ollama")

    async def status(self):
        async with httpx.AsyncClient(timeout=8.0) as client:
            version_response = await client.get(f"{self.base}/api/version")
            version_response.raise_for_status()
            # /api/ps may be unsupported by older Ollama versions.
            try:
                loaded_response = await client.get(f"{self.base}/api/ps")
                loaded_response.raise_for_status()
                loaded = [{"name": m.get("name"), "size": m.get("size"),
                           "size_vram": m.get("size_vram"), "expires_at": m.get("expires_at")}
                          for m in loaded_response.json().get("models", [])]
            except (httpx.HTTPError, ValueError, KeyError):
                loaded = None
            return {"online": True, "version": version_response.json().get("version"),
                    "loaded_models": loaded,
                    "metrics_note": "size_vram is estimated model GPU residency in bytes, not live GPU utilization"}

    async def stream_chat(self, messages: list[dict[str, str]], max_tokens: int = 384, *,
                          model: str | None = None, temperature: float | None = None,
                          top_p: float | None = None, num_ctx: int | None = None) -> AsyncIterator[str]:
        opts = {"num_predict": max_tokens}
        for key, value in (("temperature", temperature), ("top_p", top_p), ("num_ctx", num_ctx)):
            if value is not None:
                opts[key] = value
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0, connect=10.0)) as client:
            async with client.stream("POST", f"{self.base}/api/chat",
                json={"model": model or settings.ollama_model, "messages": messages, "stream": True,
                      "think": False, "options": opts}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("error"):
                        raise RuntimeError("Local inference returned an error")
                    chunk = event.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if event.get("done"):
                        break

    async def complete(self, messages: list[dict[str, str]], max_tokens: int = 384, *, model: str | None = None) -> str:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=10.0)) as client:
            response = await client.post(f"{self.base}/api/chat",
                json={"model": model or settings.ollama_model, "messages": messages, "stream": False,
                      "think": False, "options": {"num_predict": max_tokens, "temperature": 0.1}})
            response.raise_for_status()
            return str(response.json().get("message", {}).get("content", ""))
