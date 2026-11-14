"""Pydantic v2 schemas for all OpenDocs API request and response models."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator, AnyHttpUrl


class DocumentCreateRequest(BaseModel):
    url: str = Field(..., description="Target documentation URL to ingest and verify (must be http/https)")

    @field_validator("url")
    @classmethod
    def url_must_not_be_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL must not be empty")
        # Allow mock:// only for internal testing; real URLs must be http/https
        if not (v.startswith("http://") or v.startswith("https://") or v.startswith("mock://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class DocumentPreviewRequest(BaseModel):
    url: str = Field(..., description="Target documentation URL to preview")
    target_language: str = Field("Kannada", description="Target language name or code")


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


class SandboxRunRequest(BaseModel):
    code: str = Field(..., description="Source code snippet to execute")
    language: Literal["python", "bash", "javascript"] = "python"
    timeout_seconds: float = Field(5.0, ge=1.0, le=30.0)


class SandboxRunResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    execution_ms: int
    timed_out: bool
    language: str
    is_sandboxed: bool


class DiagnosticRequest(BaseModel):
    doc_id: str
    error_log: str
    failed_command: str | None = None


class DiagnosticResponse(BaseModel):
    exception_type: str
    missing_entity: str | None
    diagnosis: str
    recommended_fix_command: str | None
    cited_section: str
    anchor: str | None
    confidence: float


class MonitorRegisterRequest(BaseModel):
    doc_id: str
    url: str
    content_hash: str
    etag: str | None = None


class MonitorCheckResponse(BaseModel):
    doc_id: str
    has_changed: bool
    old_hash: str
    new_hash: str
    added_headings: list[str]
    removed_headings: list[str]
    stale_sections_invalidated: int


class TranscribeResponse(BaseModel):
    text: str
    language: str
    confidence: float
    duration_seconds: float


class TTSRequest(BaseModel):
    text: str
    lang: str = "kn"
    speed: float = 1.0


class TTSResponse(BaseModel):
    audio_base64: str
    format: str
    sample_rate: int
    duration_ms: int
    cue_points: list[dict[str, Any]]


class QARequest(BaseModel):
    doc_id: str
    question: str
    target_lang: str = "en"


class QAResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]]
    verified_commands: list[str]
    abstained: bool
    confidence: float


