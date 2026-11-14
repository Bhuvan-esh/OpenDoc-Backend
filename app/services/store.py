"""In-memory thread-safe state store for documents, jobs, proofs, and learner progress."""

from __future__ import annotations

import threading
from typing import Any
from app.core.docast import DocAST
from app.core.learning import Flashcard, QuizItem
from app.core.proof import PreservationProof
from app.models.schemas import AlignedParagraphItem


class InMemoryStore:
    """Centralized repository for documents, active jobs, ASTs, proofs, and user progress."""

    def __init__(self):
        self.documents: dict[str, dict[str, Any]] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.job_events: dict[str, list[dict[str, Any]]] = {}
        self.doc_asts: dict[str, DocAST] = {}
        self.paragraphs: dict[str, list[AlignedParagraphItem]] = {}  # key: f"{doc_id}:{lang}"
        self.proofs: dict[str, PreservationProof] = {}              # key: f"{doc_id}:{lang}"
        self.flashcards: dict[str, list[Flashcard]] = {}            # key: doc_id
        self.quizzes: dict[str, list[QuizItem]] = {}                # key: doc_id
        self.user_progress: dict[str, dict[str, Any]] = {}          # key: f"{user_token}:{doc_id}"
        self.lock = threading.Lock()

    async def save_document(self, doc_id: str, doc_data: dict[str, Any]) -> None:
        with self.lock:
            self.documents[doc_id] = doc_data

    async def get_document(self, doc_id: str) -> dict[str, Any] | None:
        return self.documents.get(doc_id)

    async def save_job(self, job_id: str, job_data: dict[str, Any]) -> None:
        with self.lock:
            self.jobs[job_id] = job_data
            if job_id not in self.job_events:
                self.job_events[job_id] = []

    async def add_job_event(self, job_id: str, event: dict[str, Any]) -> None:
        with self.lock:
            if job_id in self.job_events:
                self.job_events[job_id].append(event)

    async def get_job_events(self, job_id: str) -> list[dict[str, Any]]:
        return self.job_events.get(job_id, [])

    async def save_ast(self, doc_id: str, ast: DocAST) -> None:
        with self.lock:
            self.doc_asts[doc_id] = ast

    async def get_ast(self, doc_id: str) -> DocAST | None:
        return self.doc_asts.get(doc_id)

    async def save_content(self, doc_id: str, lang: str, paras: list[AlignedParagraphItem]) -> None:
        key = f"{doc_id}:{lang}"
        with self.lock:
            self.paragraphs[key] = paras

    async def get_content(self, doc_id: str, lang: str) -> list[AlignedParagraphItem] | None:
        key = f"{doc_id}:{lang}"
        return self.paragraphs.get(key)

    async def save_proof(self, doc_id: str, lang: str, proof: PreservationProof) -> None:
        key = f"{doc_id}:{lang}"
        with self.lock:
            self.proofs[key] = proof

    async def get_proof(self, doc_id: str, lang: str) -> PreservationProof | None:
        key = f"{doc_id}:{lang}"
        return self.proofs.get(key)

    async def save_flashcards(self, doc_id: str, cards: list[Flashcard]) -> None:
        with self.lock:
            self.flashcards[doc_id] = cards

    async def get_flashcards(self, doc_id: str) -> list[Flashcard]:
        return self.flashcards.get(doc_id, [])

    async def save_quizzes(self, doc_id: str, quizzes: list[QuizItem]) -> None:
        with self.lock:
            self.quizzes[doc_id] = quizzes

    async def get_quizzes(self, doc_id: str) -> list[QuizItem]:
        return self.quizzes.get(doc_id, [])

    async def update_user_progress(
        self,
        user_token: str,
        doc_id: str,
        section_id: str,
        status: str,
        score: float | None = None,
    ) -> dict[str, Any]:
        key = f"{user_token}:{doc_id}"
        with self.lock:
            if key not in self.user_progress:
                self.user_progress[key] = {
                    "completed_sections": set(),
                    "section_scores": {},
                }
            profile = self.user_progress[key]
            if status == "completed":
                profile["completed_sections"].add(section_id)
            if score is not None:
                profile["section_scores"][section_id] = score

            return {
                "user_token": user_token,
                "doc_id": doc_id,
                "completed_sections": list(profile["completed_sections"]),
                "section_scores": profile["section_scores"],
            }

    async def get_user_progress(self, user_token: str, doc_id: str) -> dict[str, Any]:
        key = f"{user_token}:{doc_id}"
        data = self.user_progress.get(key, {"completed_sections": set(), "section_scores": {}})
        return {
            "user_token": user_token,
            "doc_id": doc_id,
            "completed_sections": list(data.get("completed_sections", set())),
            "section_scores": data.get("section_scores", {}),
        }


# Global store instance for backend runtime
store = InMemoryStore()
