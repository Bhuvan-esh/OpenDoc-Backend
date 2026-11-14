"""Grounded Question Answering API endpoint with Command-in-Answer verification gate."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from app.models.schemas import QARequest, QAResponse
from app.services.qa import qa_service
from app.services.store import store

router = APIRouter(prefix="/api", tags=["Grounded Q&A"])


@router.post("/qa", response_model=QAResponse)
async def ask_question(req: QARequest):
    """Answer questions grounded in documentation with citation anchors and command verification."""
    ast = await store.get_ast(req.doc_id)
    if not ast:
        raise HTTPException(status_code=404, detail="Document AST not found. Please ingest the document first.")

    res = qa_service.answer_question(
        question=req.question,
        doc_ast=ast,
        target_lang=req.target_lang,
    )

    return QAResponse(
        answer=res.answer,
        citations=[c.to_dict() for c in res.citations],
        verified_commands=res.verified_commands,
        abstained=res.abstained,
        confidence=round(res.confidence, 3),
    )
