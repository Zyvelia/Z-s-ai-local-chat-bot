from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

class ChatProvider(ABC):
    @abstractmethod
    async def stream_chat(self, messages: list[dict[str, str]], max_tokens: int = 384, *,
                          model: str | None = None, temperature: float | None = None,
                          top_p: float | None = None, num_ctx: int | None = None) -> AsyncIterator[str]:
        """Yield visible assistant text chunks only."""
