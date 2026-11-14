"""
Pytest shared fixtures for OpenDocs test suite.
Provides a TestClient, a fresh in-memory store, and common mock document fixtures.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.store import store as global_store


@pytest.fixture(scope="function", autouse=True)
def reset_store():
    """
    Reset the in-memory store before each test so tests are fully isolated.
    Prevents state bleed between test cases.
    """
    global_store.documents.clear()
    global_store.jobs.clear()
    global_store.job_events.clear()
    global_store.doc_asts.clear()
    global_store.paragraphs.clear()
    global_store.proofs.clear()
    global_store.flashcards.clear()
    global_store.quizzes.clear()
    global_store.user_progress.clear()
    yield


@pytest.fixture(scope="session")
def client():
    """Shared FastAPI TestClient for the session."""
    return TestClient(app)


@pytest.fixture()
def fresh_client():
    """Per-test TestClient (use when you need a truly isolated ASGI context)."""
    return TestClient(app)


@pytest.fixture()
def mock_doc_url() -> str:
    return "mock://docs.example.com/guide"


@pytest.fixture()
def ingested_doc(client, mock_doc_url):
    """
    Ingest a mock document and return (doc_id, job_id).
    Waits briefly for the background pipeline to complete.
    """
    import time
    res = client.post("/api/documents", json={"url": mock_doc_url})
    assert res.status_code == 202
    data = res.json()
    time.sleep(0.3)   # allow background task to finish
    return data["doc_id"], data["job_id"]
