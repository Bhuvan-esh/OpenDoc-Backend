"""Sandbox execution and grounded error diagnostic route handlers."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    DiagnosticRequest,
    DiagnosticResponse,
    SandboxRunRequest,
    SandboxRunResponse,
)
from app.services.diagnostics import ErrorDiagnosticEngine
from app.services.sandbox import CodeSandbox
from app.services.store import store

router = APIRouter(prefix="/api", tags=["Code Sandbox & Diagnostics"])


@router.post("/sandbox/run", response_model=SandboxRunResponse)
async def run_code_in_sandbox(req: SandboxRunRequest):
    """Execute code snippet in ephemeral isolated sandbox environment."""
    result = await CodeSandbox.execute(
        code=req.code,
        language=req.language,
        timeout_seconds=req.timeout_seconds,
    )

    return SandboxRunResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        execution_ms=result.execution_ms,
        timed_out=result.timed_out,
        language=result.language,
        is_sandboxed=result.is_sandboxed,
    )


@router.post("/diagnostics/error", response_model=DiagnosticResponse)
async def diagnose_error(req: DiagnosticRequest):
    """Diagnose runtime error log and match against document's canonical instructions."""
    ast = await store.get_ast(req.doc_id)

    report = ErrorDiagnosticEngine.diagnose(
        error_log=req.error_log,
        doc_ast=ast,
        failed_command=req.failed_command,
    )

    return DiagnosticResponse(
        exception_type=report.exception_type,
        missing_entity=report.missing_entity,
        diagnosis=report.diagnosis,
        recommended_fix_command=report.recommended_fix_command,
        cited_section=report.cited_section,
        anchor=report.anchor,
        confidence=report.confidence,
    )
