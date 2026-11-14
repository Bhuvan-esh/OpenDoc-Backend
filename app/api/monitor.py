"""Upstream documentation monitoring endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from app.models.schemas import MonitorCheckResponse, MonitorRegisterRequest
from app.services.monitor import monitor_service
from app.services.store import store

router = APIRouter(prefix="/api/monitor", tags=["Upstream Documentation Monitoring"])


@router.post("/register", status_code=201)
async def register_source(req: MonitorRegisterRequest):
    """Register a documentation source URL for continuous change tracking."""
    monitor_service.register_source(
        doc_id=req.doc_id,
        url=req.url,
        content_hash=req.content_hash,
        etag=req.etag,
    )
    return {"status": "registered", "doc_id": req.doc_id, "url": req.url}


@router.post("/check/{doc_id}", response_model=MonitorCheckResponse)
async def check_updates(doc_id: str):
    """Trigger an on-demand upstream change detection check and cascade invalidation."""
    try:
        diff = await monitor_service.check_for_updates(doc_id=doc_id)
        return MonitorCheckResponse(
            doc_id=diff.doc_id,
            has_changed=diff.has_changed,
            old_hash=diff.old_hash,
            new_hash=diff.new_hash,
            added_headings=diff.added_headings,
            removed_headings=diff.removed_headings,
            stale_sections_invalidated=diff.stale_sections_invalidated,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
