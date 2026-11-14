"""Pydantic v2 schemas for all OpenDocs API request and response models."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class DocumentCreateRequest(BaseModel):
    url: str = Field(..., description="Target documentation URL to ingest and verify")


class DocumentCreateResponse(BaseModel):
    job_id: str
    doc_id: str
    status: str
    message: str


class JobEvent(BaseModel):
    stage: str
    status: str
    ms: int
    details: dict[str, Any] = Field(default_factory=dict)


class AlignedParagraphItem(BaseModel):
    id: str
    order_index: int
    original_text: str
    translated_text: str
    target_lang: str
    status: str  # verified_structural | verified_exact | verified_after_repair | fallback_original
    proof_badge: str
    tts_cue_points: list[dict[str, Any]] = Field(default_factory=list)


class DocumentContentResponse(BaseModel):
    doc_id: str
    target_lang: str
    paragraphs: list[AlignedParagraphItem]


class FlashcardResponse(BaseModel):
    id: str
    section_id: str
    heading: str
    front: str
    back: str
    code_snippet: str | None = None
    target_lang: str
    anchor: str | None = None


class QuizItemResponse(BaseModel):
    id: str
    section_id: str
    heading: str
    question: str
    options: list[str]
    cited_para_id: str


class QuizEvaluateRequest(BaseModel):
    selected_index: int


class QuizEvaluateResponse(BaseModel):
    is_correct: bool
    correct_index: int
    score: float
    explanation: str


class ExplainRequest(BaseModel):
    text: str
    mode: Literal["eli5", "beginner_dev", "deep_dive"] = "beginner_dev"


class ExplainResponse(BaseModel):
    explanation: str
    mode: str


class UserProgressUpdateRequest(BaseModel):
    section_id: str
    status: Literal["unvisited", "reading", "completed", "stale"]
    quiz_score: float | None = None


class UserProgressResponse(BaseModel):
    user_token: str
    doc_id: str
    completed_sections: list[str]
    section_scores: dict[str, float]


class NextCurriculumResponse(BaseModel):
    doc_id: str
    next_section: dict[str, Any] | None
    all_completed: bool


class MetricsResponse(BaseModel):
    total_documents: int
    total_spans_verified: int
    mode_a_count: int
    mode_b_count: int
    failed_count: int
    preservation_rate: float
