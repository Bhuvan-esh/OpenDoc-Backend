"""Public verification, cryptographic proofs, audit metrics, and model manifest endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from app.adapters.router import AdapterRouter
from app.api.documents import proof_engine
from app.models.schemas import MetricsResponse
from app.services.store import store

router = APIRouter(prefix="/api", tags=["Verification & Trust"])
router_adapter = AdapterRouter()


@router.get("/documents/{doc_id}/proof")
async def get_document_proof(
    doc_id: str,
    lang: str = Query("kn", description="Target language code"),
):
    """Retrieve full signed Preservation Ledger and Merkle root."""
    proof = await store.get_proof(doc_id, lang)
    if not proof:
        raise HTTPException(status_code=404, detail=f"No verification proof found for document {doc_id} in '{lang}'.")
    return proof.to_dict()


@router.get("/proof.pub")
async def get_public_key():
    """Retrieve the node's Ed25519 public key and CLI verification instructions."""
    return {
        "algorithm": "Ed25519",
        "public_key_b64": proof_engine.public_key_b64,
        "verification_tool": "verify.py",
        "instructions": "Run: python verify.py <proof.json>",
    }


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Return live system-wide preservation accuracy metrics."""
    total_docs = len(store.documents)
    total_spans = 0
    mode_a_total = 0
    mode_b_total = 0
    failed_total = 0

    for proof in store.proofs.values():
        total_spans += proof.total_spans
        mode_a_total += proof.mode_a_count
        mode_b_total += proof.mode_b_count
        failed_total += proof.failed_count

    preservation_rate = 1.0
    if total_spans > 0:
        preservation_rate = (total_spans - failed_total) / total_spans

    return MetricsResponse(
        total_documents=total_docs,
        total_spans_verified=total_spans,
        mode_a_count=mode_a_total,
        mode_b_count=mode_b_total,
        failed_count=failed_total,
        preservation_rate=round(preservation_rate, 4),
    )


@router.get("/models/manifest")
async def get_model_manifest():
    """Return model provenance, weight SHAs, and open-source licenses."""
    return {
        "service": "OpenDocs Voice & Learning Engine",
        "app_license": "Apache-2.0",
        "adapters": router_adapter.get_manifest(),
    }
