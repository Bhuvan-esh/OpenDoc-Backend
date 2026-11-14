"""Document ingestion, stage tracking, and aligned bilingual reader endpoints."""

from __future__ import annotations

import hashlib
import time
import uuid
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.adapters.router import AdapterRouter
from app.core.learning import LearningEngine
from app.core.proof import ProofEngine
from app.core.protection import ProtectedSpan, ProtectionClassifier
from app.core.segment import ParagraphSegmenter
from app.models.schemas import (
    AlignedParagraphItem,
    DocumentContentResponse,
    DocumentCreateRequest,
    DocumentCreateResponse,
)
from app.services.extract import DocumentExtractor
from app.services.fetch_guard import FetchGuard
from app.services.store import store

router = APIRouter(prefix="/api/documents", tags=["Documents & Ingestion"])
classifier = ProtectionClassifier()
proof_engine = ProofEngine()
router_adapter = AdapterRouter()


async def process_document_pipeline(job_id: str, doc_id: str, url: str, target_lang: str = "kn"):
    """Background execution of the full 11-stage ingestion, translation, and learning pipeline."""
    try:
        # 1. Fetch Stage
        start = time.perf_counter()
        # For localhost/internal test URLs, handle gracefully; for live URLs, guarded fetch
        if url.startswith("http://demo.local") or url.startswith("mock://"):
            html_content = f"<html><body><h1>FastAPI Setup</h1><p>Run pip install fastapi to proceed.</p><pre>pip install uvicorn</pre></body></html>"
            fetch_ms = 15
        else:
            fetch_res = await FetchGuard.fetch(url)
            html_content = fetch_res.content.decode("utf-8", errors="replace")
            fetch_ms = fetch_res.fetch_ms

        await store.add_job_event(job_id, {"stage": "fetch", "status": "ok", "ms": fetch_ms})

        # 2. Extraction & AST Stage
        start = time.perf_counter()
        ast = DocumentExtractor.build_docast(html_content, doc_id=doc_id)
        await store.save_ast(doc_id, ast)
        extract_ms = int((time.perf_counter() - start) * 1000)
        await store.add_job_event(job_id, {"stage": "extract", "status": "ok", "ms": extract_ms})

        # 3. Protection & Segmentation Stage
        paragraphs = ast.get_paragraphs()
        code_blocks = ast.get_code_blocks()
        all_spans: list[ProtectedSpan] = []

        # Mode A spans from code blocks
        for cb in code_blocks:
            if cb.text:
                all_spans.append(
                    ProtectedSpan.create(
                        doc_id=doc_id,
                        para_id=cb.node_id,
                        para_ordinal=cb.ordinal,
                        span_type="code_block",
                        original=cb.text,
                        start=0,
                        end=len(cb.text),
                        mode="A",
                        detection="dom",
                        confidence=1.0,
                    )
                )

        # Mode B spans from paragraph prose
        for p in paragraphs:
            if p.text:
                p_spans = classifier.classify_text(p.text, doc_id=doc_id, para_id=p.node_id, para_ordinal=p.ordinal)
                all_spans.extend(p_spans)

        await store.add_job_event(
            job_id,
            {
                "stage": "classify",
                "status": "ok",
                "total_spans": len(all_spans),
                "mode_a": len([s for s in all_spans if s.mode == "A"]),
                "mode_b": len([s for s in all_spans if s.mode == "B"]),
            },
        )

        # 4. Translation & Reassembly Stage
        start = time.perf_counter()
        adapter = router_adapter.get_adapter("en", target_lang)

        orig_paras_dict: dict[str, str] = {}
        trans_paras_dict: dict[str, str] = {}
        aligned_items: list[AlignedParagraphItem] = []

        for p in paragraphs:
            if not p.text:
                continue
            orig_paras_dict[p.node_id] = p.text
            p_spans = [s for s in all_spans if s.para_id == p.node_id and s.mode == "B"]

            # Replace with sentinels
            sentinel_str = ParagraphSegmenter.to_sentinel_string(p.text, p_spans)

            # Translate sentinel string
            res = await adapter.translate_batch([sentinel_str], src="en", tgt=target_lang)
            translated_sentinel = res.translated_texts[0]

            # Reassemble Mode B sentinels
            reassembly = ParagraphSegmenter.reassemble_sentinel_string(translated_sentinel, p_spans)
            trans_paras_dict[p.node_id] = reassembly.text

            badge = "green" if reassembly.status == "verified_exact" else "amber"
            aligned_items.append(
                AlignedParagraphItem(
                    id=p.node_id,
                    order_index=p.ordinal,
                    original_text=p.text,
                    translated_text=reassembly.text,
                    target_lang=target_lang,
                    status=reassembly.status,
                    proof_badge=badge,
                )
            )

        # Append Mode A code blocks into aligned items
        for cb in code_blocks:
            if not cb.text:
                continue
            orig_paras_dict[cb.node_id] = cb.text
            trans_paras_dict[cb.node_id] = cb.text  # Untranslated by construction
            aligned_items.append(
                AlignedParagraphItem(
                    id=cb.node_id,
                    order_index=cb.ordinal,
                    original_text=cb.text,
                    translated_text=cb.text,
                    target_lang=target_lang,
                    status="verified_structural",
                    proof_badge="green_structural",
                )
            )

        aligned_items.sort(key=lambda item: item.order_index)
        translate_ms = int((time.perf_counter() - start) * 1000)
        await store.add_job_event(job_id, {"stage": "translate", "status": "ok", "ms": translate_ms})

        # 5. Verification & Proof Stage
        proof, final_paras = proof_engine.build_proof(
            doc_id=doc_id,
            target_lang=target_lang,
            spans=all_spans,
            translated_paragraphs=trans_paras_dict,
            original_paragraphs=orig_paras_dict,
        )
        await store.save_proof(doc_id, target_lang, proof)
        await store.save_content(doc_id, target_lang, aligned_items)
        await store.add_job_event(
            job_id,
            {
                "stage": "verify",
                "status": "ok",
                "passed": proof.passed,
                "merkle_root": proof.merkle_root,
                "failed_count": proof.failed_count,
            },
        )

        # 6. Synthesize Learning Mode (Flashcards & Quizzes)
        flashcards = LearningEngine.generate_flashcards(ast, lang=target_lang)
        quizzes = LearningEngine.generate_quizzes(ast)
        await store.save_flashcards(doc_id, flashcards)
        await store.save_quizzes(doc_id, quizzes)
        await store.add_job_event(
            job_id,
            {
                "stage": "learning_synthesis",
                "status": "ok",
                "flashcards_count": len(flashcards),
                "quizzes_count": len(quizzes),
            },
        )

        # Complete job
        await store.save_document(
            doc_id,
            {
                "id": doc_id,
                "url": url,
                "status": "ready",
                "default_lang": target_lang,
            },
        )

    except Exception as exc:
        await store.add_job_event(job_id, {"stage": "pipeline", "status": "error", "error": str(exc)})
        await store.save_document(doc_id, {"id": doc_id, "url": url, "status": "failed", "error": str(exc)})


@router.post("", response_model=DocumentCreateResponse, status_code=202)
async def create_document(req: DocumentCreateRequest, background_tasks: BackgroundTasks):
    """Ingest a documentation URL, start background processing, and return job handles."""
    doc_id = hashlib.sha256(req.url.encode("utf-8")).hexdigest()[:16]
    job_id = str(uuid.uuid4())[:12]

    await store.save_job(job_id, {"job_id": job_id, "doc_id": doc_id, "url": req.url, "status": "processing"})
    await store.save_document(doc_id, {"id": doc_id, "url": req.url, "status": "queued"})

    # Launch background task
    background_tasks.add_task(process_document_pipeline, job_id, doc_id, req.url)

    return DocumentCreateResponse(
        job_id=job_id,
        doc_id=doc_id,
        status="accepted",
        message="Document queued for guarded ingestion, verification, and learning synthesis.",
    )


@router.get("/jobs/{job_id}/events")
async def get_job_events(job_id: str):
    """Return chronological processing milestones and stage events."""
    events = await store.get_job_events(job_id)
    if not events:
        return {"job_id": job_id, "status": "pending", "events": []}
    return {"job_id": job_id, "events": events}


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """Retrieve document metadata and status."""
    doc = await store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


@router.get("/{doc_id}/content", response_model=DocumentContentResponse)
async def get_document_content(doc_id: str, lang: str = Query("kn", description="Target language code")):
    """Return aligned bilingual paragraphs with verification proof badges."""
    paras = await store.get_content(doc_id, lang)
    if not paras:
        raise HTTPException(status_code=404, detail=f"No translated content available for document {doc_id} in '{lang}'.")
    return DocumentContentResponse(doc_id=doc_id, target_lang=lang, paragraphs=paras)
