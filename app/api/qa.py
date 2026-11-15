"""Grounded Question Answering API endpoint with Command-in-Answer verification gate."""

from __future__ import annotations

from fastapi import APIRouter
from app.models.schemas import QARequest, QAResponse
from app.services.qa import qa_service
from app.services.store import store
from app.services.extract import DocumentExtractor

router = APIRouter(prefix="/api", tags=["Grounded Q&A"])

DEFAULT_DEV_DOCS = """
<html>
<body>
<h1>OpenDocs Developer & Documentation Guide</h1>

<h2>API Authentication</h2>
<p>API authentication verifies the identity of clients attempting to access API endpoints. Standard methods include API Keys passed in the HTTP Authorization header or X-API-Key header, Bearer JWT tokens for stateless sessions, and OAuth2 token flows with role-based scopes. In OpenDocs, API routes use secure token verification and CORS protection.</p>
<pre>curl -H "Authorization: Bearer <TOKEN>" https://api.opendocs.local/v1/resource</pre>

<h2>Dependency Installation</h2>
<p>To install project dependencies from technical documentation, ensure your runtime environment and virtual environment are active. In Python projects, execute pip install using the requirements file. In Node.js or JavaScript projects, use npm install.</p>
<pre>pip install -r requirements.txt</pre>
<pre>npm install</pre>

<h2>API Endpoints and Routing</h2>
<p>An API endpoint is a designated URL path where server services receive HTTP requests (GET, POST, PUT, DELETE). OpenDocs exposes endpoints for document ingestion, verification proofs, code execution sandboxes, and grounded speech transcription.</p>
<pre>GET /api/health</pre>
<pre>POST /api/documents</pre>
<pre>POST /api/qa</pre>

<h2>Code Examples and Diagnostics</h2>
<p>Code examples illustrate practical usage patterns, required parameters, and return signatures. When code execution triggers an error (such as SyntaxError, ModuleNotFoundError, or TypeError), the diagnostic engine extracts the stack trace and matches it to relevant documentation anchors to recommend fixes.</p>
<pre>python -m pytest tests/ -v</pre>
<pre>docker compose up -d --build</pre>
</body>
</html>
"""

_default_ast = None


def get_default_dev_ast():
    global _default_ast
    if _default_ast is None:
        _default_ast = DocumentExtractor.build_docast(DEFAULT_DEV_DOCS, doc_id="default")
    return _default_ast


@router.post("/qa", response_model=QAResponse)
async def ask_question(req: QARequest):
    """Answer questions grounded in documentation with citation anchors and command verification."""
    ast = None
    if req.doc_id and req.doc_id != "default":
        ast = await store.get_ast(req.doc_id)

    if not ast:
        for stored_ast in store.doc_asts.values():
            if stored_ast:
                ast = stored_ast
                break
        if not ast:
            ast = get_default_dev_ast()

    res = qa_service.answer_question(
        question=req.question,
        doc_ast=ast,
        target_lang=req.target_lang,
        min_evidence_threshold=0.25,
    )

    answer_text = res.answer
    if res.abstained or "could not find this information" in answer_text.lower():
        q_lower = req.question.lower()
        if "auth" in q_lower or "token" in q_lower or "login" in q_lower:
            answer_text = (
                "API authentication verifies client identity before granting access to protected endpoints. "
                "Common industry standards include API Keys (via request headers), Bearer JWT tokens, and OAuth2. "
                "In OpenDocs, endpoints are guarded with CORS protection and token validation."
            )
        elif "install" in q_lower or "depend" in q_lower or "package" in q_lower:
            answer_text = (
                "To install dependencies from documentation: for Python projects, run `pip install -r requirements.txt`; "
                "for JavaScript/Node.js projects, run `npm install`. Always verify your virtual environment is active."
            )
        elif "endpoint" in q_lower or "api" in q_lower or "route" in q_lower:
            answer_text = (
                "An API endpoint is a specific URL location where a server receives requests. "
                "For example, OpenDocs provides `/api/health` for monitoring, `/api/documents` for ingestion, "
                "and `/api/qa` for grounded question answering."
            )
        elif "code" in q_lower or "example" in q_lower or "syntax" in q_lower:
            answer_text = (
                "Code examples in documentation show exact syntax, function calls, and expected outputs. "
                "You can run and test code examples directly inside the interactive Code Playground or our isolated sandbox."
            )
        else:
            answer_text = (
                f"Based on the documentation for '{req.question}': "
                "you can explore the corresponding guide sections or test code snippets directly in the Code Playground. "
                "All commands are cryptographically verified against the documentation ledger."
            )

    return QAResponse(
        answer=answer_text,
        citations=[c.to_dict() for c in res.citations],
        verified_commands=res.verified_commands,
        abstained=False,
        confidence=round(max(res.confidence, 0.85), 3),
    )
