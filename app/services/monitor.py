"""Upstream Documentation Monitoring: Lightweight ETag polling, AST diffing, and stale invalidation."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.docast import DocAST
from app.services.extract import DocumentExtractor
from app.services.fetch_guard import FetchGuard
from app.services.store import store


@dataclass
class UpstreamDiffResult:
    """Outcome of an upstream change check."""

    doc_id: str
    url: str
    has_changed: bool
    old_hash: str
    new_hash: str
    added_headings: list[str] = field(default_factory=list)
    removed_headings: list[str] = field(default_factory=list)
    stale_sections_invalidated: int = 0
    checked_at_epoch: float = field(default_factory=time.time)


class UpstreamMonitorService:
    """Periodically or on-demand checks upstream documentation sources for changes."""

    def __init__(self):
        # doc_id -> metadata {url, etag, last_modified, content_hash, last_checked}
        self.monitored_sources: dict[str, dict[str, Any]] = {}

    def register_source(self, doc_id: str, url: str, content_hash: str, etag: str | None = None) -> None:
        """Register a document for continuous upstream monitoring."""
        self.monitored_sources[doc_id] = {
            "doc_id": doc_id,
            "url": url,
            "etag": etag,
            "content_hash": content_hash,
            "last_checked": time.time(),
            "change_count": 0,
        }

    async def check_for_updates(self, doc_id: str, force_html: str | None = None) -> UpstreamDiffResult:
        """Inspect source URL or provided updated HTML, diff ASTs, and invalidate stale learner progress."""
        source = self.monitored_sources.get(doc_id)
        if not source and not force_html:
            raise ValueError(f"Document {doc_id} is not registered for monitoring.")

        url = source["url"] if source else "mock://local-doc"
        old_hash = source.get("content_hash", "") if source else ""

        # Fetch new content
        if force_html is not None:
            new_content = force_html
            new_hash = hashlib.sha256(new_content.encode("utf-8")).hexdigest()
        else:
            fetch_res = await FetchGuard.fetch(url)
            new_content = fetch_res.content.decode("utf-8", errors="replace")
            new_hash = fetch_res.content_sha256

        if old_hash and old_hash == new_hash:
            # Document is unchanged
            return UpstreamDiffResult(
                doc_id=doc_id,
                url=url,
                has_changed=False,
                old_hash=old_hash,
                new_hash=new_hash,
                stale_sections_invalidated=0,
            )

        # Document changed! Compute AST diff
        old_ast = await store.get_ast(doc_id)
        old_headings = set()
        if old_ast:
            old_headings = {h.text for h in old_ast.iter_nodes() if h.kind == "heading" and h.text}

        new_ast = DocumentExtractor.build_docast(new_content, doc_id=doc_id)
        new_headings = {h.text for h in new_ast.iter_nodes() if h.kind == "heading" and h.text}

        added = sorted(new_headings - old_headings)
        removed = sorted(old_headings - new_headings)

        # Cascading Invalidation: Mark affected sections as 'stale' in user progress
        invalidated_count = 0
        for key, profile in store.user_progress.items():
            if key.endswith(f":{doc_id}"):
                # User has progress on this doc; mark progress as stale
                if "stale_sections" not in profile:
                    profile["stale_sections"] = []
                profile["stale_sections"].extend(added)
                invalidated_count += 1

        # Update stored AST and source record
        await store.save_ast(doc_id, new_ast)
        if doc_id in self.monitored_sources:
            self.monitored_sources[doc_id]["content_hash"] = new_hash
            self.monitored_sources[doc_id]["last_checked"] = time.time()
            self.monitored_sources[doc_id]["change_count"] += 1

        return UpstreamDiffResult(
            doc_id=doc_id,
            url=url,
            has_changed=True,
            old_hash=old_hash,
            new_hash=new_hash,
            added_headings=added,
            removed_headings=removed,
            stale_sections_invalidated=invalidated_count,
        )


# Global monitor service instance
monitor_service = UpstreamMonitorService()
