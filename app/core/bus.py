"""InferenceBus: Memory-aware concurrency and execution scheduler for AI models."""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine


class InferenceBus:
    """Controls model execution concurrency, resident memory, and timeouts."""

    def __init__(self, max_concurrent_heavy_jobs: int = 2, default_timeout_seconds: float = 30.0):
        self.semaphore = asyncio.Semaphore(max_concurrent_heavy_jobs)
        self.default_timeout = default_timeout_seconds
        self.resident_models: set[str] = set()

    async def run(
        self,
        model_id: str,
        coro_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a model inference task through the concurrency semaphore with timeout."""
        effective_timeout = timeout or self.default_timeout
        async with self.semaphore:
            self.resident_models.add(model_id)
            try:
                return await asyncio.wait_for(
                    coro_fn(*args, **kwargs),
                    timeout=effective_timeout,
                )
            finally:
                pass

    def get_status(self) -> dict[str, Any]:
        """Return bus health, resident models, and active concurrency slots."""
        return {
            "resident_models": list(self.resident_models),
            "available_slots": self.semaphore._value,
        }
