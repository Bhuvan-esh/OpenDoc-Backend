"""Segmentation and reassembly of prose runs with protected spans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.core.protection import ProtectedSpan


@dataclass
class ProseRun:
    """A segment of purely natural language text destined for translation."""

    run_id: str
    text: str
    run_ordinal: int
    start: int
    end: int


@dataclass
class ReassemblyResult:
    """Output of paragraph reconstruction with validation metadata."""

    text: str
    all_sentinels_found: bool
    missing_sentinels: list[str]
    repaired_sentinels: list[str]
    status: Literal["verified_exact", "verified_after_repair", "failed"]


class ParagraphSegmenter:
    """Slices paragraphs around protected spans and handles reconstruction."""

    SENTINEL_RE = re.compile(r"⟦([a-zA-Z0-9]+)⟧")

    @classmethod
    def segment(
        cls,
        text: str,
        spans: list[ProtectedSpan],
        para_id: str,
    ) -> list[ProseRun | ProtectedSpan]:
        """Produce an ordered list of alternating ProseRun and ProtectedSpan items."""
        if not spans:
            return [ProseRun(run_id=f"{para_id}:r0", text=text, run_ordinal=0, start=0, end=len(text))]

        parts: list[ProseRun | ProtectedSpan] = []
        current_offset = 0
        run_ordinal = 0

        for sp in spans:
            if sp.start > current_offset:
                prose_text = text[current_offset:sp.start]
                parts.append(
                    ProseRun(
                        run_id=f"{para_id}:r{run_ordinal}",
                        text=prose_text,
                        run_ordinal=run_ordinal,
                        start=current_offset,
                        end=sp.start,
                    )
                )
                run_ordinal += 1

            parts.append(sp)
            current_offset = sp.end

        if current_offset < len(text):
            prose_text = text[current_offset:]
            parts.append(
                ProseRun(
                    run_id=f"{para_id}:r{run_ordinal}",
                    text=prose_text,
                    run_ordinal=run_ordinal,
                    start=current_offset,
                    end=len(text),
                )
            )

        return parts

    @classmethod
    def to_sentinel_string(cls, text: str, spans: list[ProtectedSpan]) -> str:
        """Replace all Mode B spans in the text with their atomic sentinels."""
        if not spans:
            return text

        # Spans must be ordered by start position
        sorted_spans = sorted(spans, key=lambda s: s.start)
        result: list[str] = []
        current_offset = 0

        for sp in sorted_spans:
            if sp.start > current_offset:
                result.append(text[current_offset:sp.start])
            result.append(sp.sentinel or sp.original)
            current_offset = sp.end

        if current_offset < len(text):
            result.append(text[current_offset:])

        return "".join(result)

    @classmethod
    def reassemble_sentinel_string(
        cls,
        translated_text: str,
        spans: list[ProtectedSpan],
    ) -> ReassemblyResult:
        """Replace sentinels in translated text with original values and verify survival."""
        reconstructed = translated_text
        missing: list[str] = []
        repaired: list[str] = []

        for sp in spans:
            if not sp.sentinel:
                continue

            # Exact match check
            if sp.sentinel in reconstructed:
                # Replace exactly once to preserve arity
                reconstructed = reconstructed.replace(sp.sentinel, sp.original, 1)
            else:
                # Check if sentinel lost brackets or was whitespace-split (e.g., ⟦ k1 ⟧)
                loose_re = re.compile(rf"⟦\s*{re.escape(sp.sentinel[1:-1])}\s*⟧")
                if loose_re.search(reconstructed):
                    reconstructed = loose_re.sub(sp.original, reconstructed, count=1)
                    repaired.append(sp.sentinel)
                else:
                    missing.append(sp.sentinel)

        if missing:
            # Sentinel was dropped by model -> Fail verification
            return ReassemblyResult(
                text=reconstructed,
                all_sentinels_found=False,
                missing_sentinels=missing,
                repaired_sentinels=repaired,
                status="failed",
            )

        if repaired:
            return ReassemblyResult(
                text=reconstructed,
                all_sentinels_found=True,
                missing_sentinels=[],
                repaired_sentinels=repaired,
                status="verified_after_repair",
            )

        return ReassemblyResult(
            text=reconstructed,
            all_sentinels_found=True,
            missing_sentinels=[],
            repaired_sentinels=[],
            status="verified_exact",
        )
