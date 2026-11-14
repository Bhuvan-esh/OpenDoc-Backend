"""Hierarchical Document Abstract Syntax Tree (DocAST) definition and traversals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Literal

NodeKind = Literal[
    "root",
    "heading",
    "paragraph",
    "list",
    "list_item",
    "code_block",
    "inline_code",
    "table",
    "table_row",
    "table_cell",
    "link",
    "admonition",
    "text",
    "thematic_break",
]


@dataclass
class DocAST:
    """The single source of truth for parsed and annotated documentation."""

    node_id: str
    kind: NodeKind
    text: str | None = None
    level: int | None = None  # 1..6 for headings
    children: list[DocAST] = field(default_factory=list)
    href: str | None = None  # destination URL: protected, never translated
    anchor: str | None = None  # section anchor id for citations (#install, etc.)
    heading_path: tuple[str, ...] = ()  # citation breadcrumb: ("Setup", "Linux")
    ordinal: int = 0  # reading order index (a11y and deterministic indexing)
    hard_protected: bool = False  # structural protection (code_block, kbd, math)
    confidence: float = 1.0
    notes: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        kind: NodeKind,
        doc_id: str,
        ordinal: int,
        text: str | None = None,
        level: int | None = None,
        href: str | None = None,
        anchor: str | None = None,
        heading_path: tuple[str, ...] = (),
        hard_protected: bool = False,
        children: list[DocAST] | None = None,
    ) -> DocAST:
        """Construct a deterministic DocAST node."""
        node_seed = f"{doc_id}:{ordinal}:{kind}:{text or ''}"
        node_id = hashlib.sha256(node_seed.encode("utf-8")).hexdigest()[:16]
        return cls(
            node_id=node_id,
            kind=kind,
            text=text,
            level=level,
            children=children or [],
            href=href,
            anchor=anchor,
            heading_path=heading_path,
            ordinal=ordinal,
            hard_protected=hard_protected,
        )

    def iter_nodes(self) -> Iterator[DocAST]:
        """Depth-first traversal over all AST nodes."""
        yield self
        for child in self.children:
            yield from child.iter_nodes()

    def get_paragraphs(self) -> list[DocAST]:
        """Return all translatable paragraph-level nodes."""
        return [
            node
            for node in self.iter_nodes()
            if node.kind in ("paragraph", "list_item", "table_cell")
            and node.text
            and node.text.strip()
        ]

    def get_code_blocks(self) -> list[DocAST]:
        """Return all structurally protected code blocks."""
        return [node for node in self.iter_nodes() if node.kind == "code_block"]

    def full_text(self) -> str:
        """Aggregate full text of node and descendants."""
        parts: list[str] = []
        if self.text:
            parts.append(self.text)
        for child in self.children:
            parts.append(child.full_text())
        return " ".join(parts).strip()

    def to_dict(self) -> dict[str, Any]:
        """Serialize AST to standard dictionary."""
        d = asdict(self)
        d["heading_path"] = list(self.heading_path)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocAST:
        """Deserialize AST from dictionary."""
        children = [cls.from_dict(c) for c in data.get("children", [])]
        heading_path = tuple(data.get("heading_path", ()))
        return cls(
            node_id=data["node_id"],
            kind=data["kind"],
            text=data.get("text"),
            level=data.get("level"),
            children=children,
            href=data.get("href"),
            anchor=data.get("anchor"),
            heading_path=heading_path,
            ordinal=data.get("ordinal", 0),
            hard_protected=data.get("hard_protected", False),
            confidence=data.get("confidence", 1.0),
            notes=data.get("notes", []),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
