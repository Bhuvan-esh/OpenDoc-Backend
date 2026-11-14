"""Grounded Error Diagnostic Engine: Maps stack traces to canonical doc instructions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.docast import DocAST


@dataclass
class DiagnosticReport:
    """Grounded remediation and explanation for a runtime or build error."""

    exception_type: str
    missing_entity: str | None
    diagnosis: str
    recommended_fix_command: str | None
    cited_section: str
    anchor: str | None
    confidence: float


class ErrorDiagnosticEngine:
    """Parses stack traces and matches them against document anchors and command blocks."""

    # Common exception patterns
    PYTHON_MODULE_RE = re.compile(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]")
    PYTHON_IMPORT_RE = re.compile(r"ImportError:\s+cannot import name ['\"]([^'\"]+)['\"]")
    PYTHON_FILE_RE = re.compile(r"FileNotFoundError:.*['\"]([^'\"]+)['\"]")
    NODE_MODULE_RE = re.compile(r"Cannot find module ['\"]([^'\"]+)['\"]")
    COMMAND_NOT_FOUND_RE = re.compile(
        r"(?:(?:bash|sh|zsh)?:\s*([\w-]+):\s*command not found|command not found:\s*['\"]?([\w-]+)['\"]?|['\"]?([\w-]+)['\"]?\s+is not recognized as)",
        re.IGNORECASE,
    )

    @classmethod
    def diagnose(
        cls,
        error_log: str,
        doc_ast: DocAST | None = None,
        failed_command: str | None = None,
    ) -> DiagnosticReport:
        """Parse error logs, extract primitives, and locate grounded fix in DocAST."""
        exc_type = "RuntimeError"
        missing_entity: str | None = None

        # 1. ModuleNotFoundError detection
        match = cls.PYTHON_MODULE_RE.search(error_log)
        if match:
            exc_type = "ModuleNotFoundError"
            missing_entity = match.group(1)
        elif cls.NODE_MODULE_RE.search(error_log):
            match = cls.NODE_MODULE_RE.search(error_log)
            exc_type = "ModuleNotFoundError"
            missing_entity = match.group(1)
        elif cls.COMMAND_NOT_FOUND_RE.search(error_log):
            match = cls.COMMAND_NOT_FOUND_RE.search(error_log)
            exc_type = "CommandNotFound"
            # Get first non-empty group
            missing_entity = next((g for g in match.groups() if g), None)
            match = cls.COMMAND_NOT_FOUND_RE.search(error_log)
            exc_type = "CommandNotFound"
            missing_entity = match.group(1)
        elif cls.PYTHON_IMPORT_RE.search(error_log):
            match = cls.PYTHON_IMPORT_RE.search(error_log)
            exc_type = "ImportError"
            missing_entity = match.group(1)

        # 2. Search DocAST for matching command / installation instructions
        recommended_fix: str | None = None
        cited_section = "General Troubleshooting"
        anchor: str | None = None
        confidence = 0.70

        if doc_ast and missing_entity:
            # Look for install commands mentioning the missing module
            for node in doc_ast.iter_nodes():
                if node.kind == "code_block" and node.text:
                    if missing_entity.lower() in node.text.lower():
                        # Extract the specific line
                        for line in node.text.splitlines():
                            if missing_entity.lower() in line.lower() and any(
                                cmd in line.lower() for cmd in ("pip", "npm", "yarn", "pnpm", "install")
                            ):
                                recommended_fix = line.strip()
                                cited_section = " > ".join(node.heading_path) if node.heading_path else "Installation"
                                anchor = node.anchor
                                confidence = 0.95
                                break
                    if recommended_fix:
                        break

        # Fallback heuristic if not explicitly found in code block
        if not recommended_fix and missing_entity:
            if exc_type == "ModuleNotFoundError":
                recommended_fix = f"pip install {missing_entity}"
            elif exc_type == "CommandNotFound":
                recommended_fix = f"npm install -g {missing_entity}"

        # 3. Construct explanatory diagnosis
        if exc_type == "ModuleNotFoundError":
            diagnosis = (
                f"The environment is missing the required dependency '{missing_entity}'. "
                f"This occurs when the module has not been installed in the active environment."
            )
        elif exc_type == "CommandNotFound":
            diagnosis = (
                f"The command '{missing_entity}' is not installed or not available on your system PATH."
            )
        elif exc_type == "ImportError":
            diagnosis = (
                f"Failed to import '{missing_entity}'. This usually indicates an outdated package version "
                f"or a breaking API rename."
            )
        else:
            diagnosis = "An unexpected runtime error occurred during snippet execution."

        return DiagnosticReport(
            exception_type=exc_type,
            missing_entity=missing_entity,
            diagnosis=diagnosis,
            recommended_fix_command=recommended_fix,
            cited_section=cited_section,
            anchor=anchor,
            confidence=confidence,
        )
