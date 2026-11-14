"""Grounded Q&A Service with Appendix B abstention rule and Command-in-Answer verification gate."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.docast import DocAST
from app.core.protection import ProtectionClassifier


@dataclass
class Citation:
    """Document reference supporting an answer."""

    node_id: str
    heading: str
    anchor: str | None
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "heading": self.heading,
            "anchor": self.anchor,
            "snippet": self.snippet,
        }


@dataclass
class QAResult:
    """Structured Q&A answer with citations and verified command list."""

    answer: str
    citations: list[Citation]
    verified_commands: list[str]
    abstained: bool
    confidence: float


class GroundedQAService:
    """Performs retrieval, evidence thresholding, and command verification for Q&A."""

    ABSTENTION_MESSAGE = "I could not find this information in the documentation page you provided."

    def __init__(self):
        self.classifier = ProtectionClassifier()

    def answer_question(
        self,
        question: str,
        doc_ast: DocAST,
        target_lang: str = "en",
        min_evidence_threshold: float = 0.50,
    ) -> QAResult:
        """Answer question grounded in DocAST, abstaining when evidence is absent."""
        q_words = set(re.findall(r"\w+", question.lower()))
        # Remove common stop words
        q_words -= {"how", "do", "i", "what", "is", "the", "to", "for", "in", "a", "an", "on", "with"}

        best_nodes: list[tuple[float, Any]] = []

        # 1. Hybrid semantic/keyword retrieval over DocAST nodes (including heading breadcrumbs)
        for node in doc_ast.iter_nodes():
            if node.kind in ("paragraph", "code_block", "list_item", "heading") and node.text:
                full_search_text = (node.text + " " + " ".join(node.heading_path)).lower()
                node_words = set(re.findall(r"\w+", full_search_text))

                # Direct match and prefix/stem match
                match_count = 0
                for qw in q_words:
                    if qw in node_words or any(nw.startswith(qw) or qw.startswith(nw) for nw in node_words if len(nw) >= 3):
                        match_count += 1

                if match_count > 0:
                    score = match_count / len(q_words)
                    best_nodes.append((score, node))

        best_nodes.sort(key=lambda x: x[0], reverse=True)

        # 2. Appendix B Abstention Rule
        if not best_nodes or best_nodes[0][0] < min_evidence_threshold:
            return QAResult(
                answer=self.ABSTENTION_MESSAGE,
                citations=[],
                verified_commands=[],
                abstained=True,
                confidence=0.0,
            )

        top_score, top_node = best_nodes[0]
        heading_title = " > ".join(top_node.heading_path) if top_node.heading_path else "Overview"

        # Locate any accompanying code block under the same heading for complete actionable guidance
        accompanying_code: str | None = None
        for n in doc_ast.iter_nodes():
            if n.kind == "code_block" and n.heading_path == top_node.heading_path and n.text:
                accompanying_code = n.text
                break

        # 3. Assemble Grounded Answer
        if top_node.kind == "code_block":
            answer_text = (
                f"According to the documentation under '{heading_title}', you should execute:\n\n"
                f"```bash\n{top_node.text}\n```"
            )
        elif accompanying_code:
            answer_text = (
                f"Under section '{heading_title}', the documentation states:\n\n"
                f"> {top_node.text}\n\n"
                f"Execute the prescribed command:\n"
                f"```bash\n{accompanying_code}\n```"
            )
        else:
            answer_text = (
                f"Under section '{heading_title}', the documentation states:\n\n"
                f"> {top_node.text}"
            )


        citations = [
            Citation(
                node_id=top_node.node_id,
                heading=heading_title,
                anchor=top_node.anchor,
                snippet=top_node.text[:120] + ("..." if len(top_node.text) > 120 else ""),
            )
        ]

        # 4. Command-in-Answer Verification Gate
        # Extract commands from doc to build ground-truth command registry
        registered_commands: set[str] = set()
        for node in doc_ast.iter_nodes():
            if node.kind == "code_block" and node.text:
                for line in node.text.splitlines():
                    if line.strip():
                        registered_commands.add(line.strip())

        # Check commands in answer against registered set
        answer_spans = self.classifier.classify_text(
            answer_text,
            doc_id=doc_ast.node_id,
            para_id="ans",
            para_ordinal=0,
        )
        verified_cmds: list[str] = []

        for span in answer_spans:
            if span.span_type in ("command", "code_block"):
                # Must be substantiated by document code blocks
                if any(span.original in cmd or cmd in span.original for cmd in registered_commands):
                    verified_cmds.append(span.original)

        # Also extract commands directly from fenced blocks in the answer
        fenced_cmds = re.findall(r"```(?:bash|sh)?\n(.*?)\n```", answer_text, re.DOTALL)
        for block in fenced_cmds:
            for line in block.splitlines():
                line_str = line.strip()
                if line_str and any(line_str in cmd or cmd in line_str for cmd in registered_commands):
                    if line_str not in verified_cmds:
                        verified_cmds.append(line_str)

        return QAResult(
            answer=answer_text,
            citations=citations,
            verified_commands=verified_cmds,
            abstained=False,
            confidence=top_score,
        )


# Global QA service instance
qa_service = GroundedQAService()
