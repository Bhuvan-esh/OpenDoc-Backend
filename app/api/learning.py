"""AI Documentation Learning Mode endpoints: Flashcards, Quizzes, Curriculum DAG, and Explainer."""

from __future__ import annotations

from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Response

from app.core.learning import CurriculumDAG, LearningEngine
from app.models.schemas import (
    ExplainRequest,
    ExplainResponse,
    FlashcardResponse,
    NextCurriculumResponse,
    QuizEvaluateRequest,
    QuizEvaluateResponse,
    QuizItemResponse,
    UserProgressResponse,
    UserProgressUpdateRequest,
)
from app.services.store import store

router = APIRouter(prefix="/api", tags=["AI Learning Engine"])


@router.get("/documents/{doc_id}/flashcards", response_model=list[FlashcardResponse])
async def get_flashcards(doc_id: str):
    """Retrieve generated flashcards for a document."""
    cards = await store.get_flashcards(doc_id)
    if not cards:
        # Check if AST exists to generate on-demand
        ast = await store.get_ast(doc_id)
        if ast:
            cards = LearningEngine.generate_flashcards(ast)
            await store.save_flashcards(doc_id, cards)
        else:
            raise HTTPException(status_code=404, detail="Document not found or no flashcards available.")

    return [
        FlashcardResponse(
            id=c.id,
            section_id=c.section_id,
            heading=c.heading,
            front=c.front,
            back=c.back,
            code_snippet=c.code_snippet,
            target_lang=c.target_lang,
            anchor=c.anchor,
        )
        for c in cards
    ]


@router.get("/documents/{doc_id}/flashcards/export")
async def export_flashcards(
    doc_id: str,
    format: Literal["anki", "markdown"] = Query("anki", description="Export format: 'anki' (TSV) or 'markdown'"),
):
    """Export flashcard deck directly into Anki TSV or Obsidian Markdown."""
    cards = await store.get_flashcards(doc_id)
    if not cards:
        raise HTTPException(status_code=404, detail="No flashcards available to export.")

    if format == "anki":
        tsv_content = LearningEngine.export_flashcards_anki_tsv(cards)
        return Response(
            content=tsv_content,
            media_type="text/tab-separated-values",
            headers={"Content-Disposition": f'attachment; filename="opendocs_{doc_id}_anki.tsv"'},
        )
    else:
        md_content = LearningEngine.export_flashcards_markdown(cards)
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="opendocs_{doc_id}_deck.md"'},
        )


@router.get("/documents/{doc_id}/quizzes", response_model=list[QuizItemResponse])
async def get_quizzes(doc_id: str):
    """Retrieve grounded multiple-choice assessment questions for a document."""
    quizzes = await store.get_quizzes(doc_id)
    if not quizzes:
        ast = await store.get_ast(doc_id)
        if ast:
            quizzes = LearningEngine.generate_quizzes(ast)
            await store.save_quizzes(doc_id, quizzes)
        else:
            raise HTTPException(status_code=404, detail="Document not found or no quizzes available.")

    return [
        QuizItemResponse(
            id=q.id,
            section_id=q.section_id,
            heading=q.heading,
            question=q.question,
            options=q.options,
            cited_para_id=q.cited_para_id,
        )
        for q in quizzes
    ]


@router.post("/quizzes/{quiz_id}/evaluate", response_model=QuizEvaluateResponse)
async def evaluate_quiz(quiz_id: str, req: QuizEvaluateRequest):
    """Evaluate learner's quiz selection and return grounded citation explanation."""
    # Search for quiz across stored quizzes
    target_quiz = None
    for quiz_list in store.quizzes.values():
        for q in quiz_list:
            if q.id == quiz_id:
                target_quiz = q
                break
        if target_quiz:
            break

    if not target_quiz:
        raise HTTPException(status_code=404, detail="Quiz question not found.")

    is_correct = req.selected_index == target_quiz.correct_index
    score = 1.0 if is_correct else 0.0

    return QuizEvaluateResponse(
        is_correct=is_correct,
        correct_index=target_quiz.correct_index,
        score=score,
        explanation=target_quiz.explanation,
    )


@router.post("/documents/{doc_id}/explain", response_model=ExplainResponse)
async def explain_concept(doc_id: str, req: ExplainRequest):
    """Multi-level conceptual simplification (ELI5, Developer, Deep Dive)."""
    explanation = LearningEngine.explain_concept(req.text, mode=req.mode)
    return ExplainResponse(explanation=explanation, mode=req.mode)


@router.post("/users/{user_token}/progress", response_model=UserProgressResponse)
async def update_progress(
    user_token: str,
    doc_id: str = Query(..., description="Document ID"),
    req: UserProgressUpdateRequest = ...,
):
    """Record learner section reading status and quiz assessment scores."""
    updated = await store.update_user_progress(
        user_token=user_token,
        doc_id=doc_id,
        section_id=req.section_id,
        status=req.status,
        score=req.quiz_score,
    )
    return UserProgressResponse(
        user_token=user_token,
        doc_id=doc_id,
        completed_sections=updated["completed_sections"],
        section_scores=updated["section_scores"],
    )


@router.get("/users/{user_token}/progress", response_model=UserProgressResponse)
async def get_progress(user_token: str, doc_id: str = Query(..., description="Document ID")):
    """Retrieve user completion and score history across sections."""
    data = await store.get_user_progress(user_token=user_token, doc_id=doc_id)
    return UserProgressResponse(
        user_token=user_token,
        doc_id=doc_id,
        completed_sections=data["completed_sections"],
        section_scores=data["section_scores"],
    )


@router.get("/documents/{doc_id}/curriculum/next", response_model=NextCurriculumResponse)
async def get_next_recommended_section(
    doc_id: str,
    user_token: str = Query("guest", description="User token"),
):
    """Calculate and return the next recommended document section using the prerequisite DAG."""
    ast = await store.get_ast(doc_id)
    if not ast:
        raise HTTPException(status_code=404, detail="Document AST not found.")

    progress = await store.get_user_progress(user_token=user_token, doc_id=doc_id)
    completed_ids = set(progress.get("completed_sections", []))

    # Build sections list from AST
    sections = []
    for node in ast.iter_nodes():
        if node.kind in ("heading", "paragraph", "code_block"):
            sections.append({
                "id": node.node_id,
                "heading": " > ".join(node.heading_path) if node.heading_path else node.kind,
                "order_index": node.ordinal,
                "prerequisites": [],
            })

    dag = CurriculumDAG(sections)
    next_sec = dag.get_next_recommended_section(completed_ids)

    return NextCurriculumResponse(
        doc_id=doc_id,
        next_section=next_sec,
        all_completed=next_sec is None and len(completed_ids) > 0,
    )
