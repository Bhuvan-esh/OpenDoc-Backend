"""Base protocol and abstractions for translation and NLP adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from pydantic import BaseModel


class TranslationResult(BaseModel):
    """Result of a translation batch call with provenance metadata."""

    translated_texts: list[str]
    adapter_id: str
    model_sha: str
    target_lang: str
    execution_ms: int
    cache_hits: int = 0


@runtime_checkable
class TranslatorAdapter(Protocol):
    """Protocol for translation models (local open-weight and API fallbacks)."""

    id: str
    model_sha: str
    license: str
    origin: str  # "local" | "api" | "mock"

    def supports(self, src: str, tgt: str) -> bool:
        """Check if language pair is supported."""
        ...

    async def translate_batch(
        self,
        texts: list[str],
        src: str,
        tgt: str,
        context: list[str] | None = None,
    ) -> TranslationResult:
        """Translate a batch of prose runs while preserving surrounding context."""
        ...
