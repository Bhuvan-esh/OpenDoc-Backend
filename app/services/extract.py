"""HTML extraction, sanitization, and DocAST hierarchy builder."""

from __future__ import annotations

import re
from bs4 import BeautifulSoup, NavigableString, Tag

from app.core.docast import DocAST

# Tags that represent structural code and must never be exposed to translation
HARD_PROTECTED_TAGS = {"pre", "code", "kbd", "samp", "var", "math"}

# Classes / attributes indicating non-translatable technical content
NO_TRANSLATE_SIGNALS = {
    "notranslate", "no-translate", "literal", "highlight", "code",
    "shell", "terminal", "console", "cmdline"
}


class DocumentExtractor:
    """Extracts clean text and builds a hierarchical DocAST from raw HTML."""

    @classmethod
    def is_node_hard_protected(cls, tag: Tag) -> bool:
        """Check if an HTML element should be structurally protected by construction."""
        if tag.name in HARD_PROTECTED_TAGS:
            return True

        if tag.get("translate") == "no":
            return True

        classes = tag.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()

        for c in classes:
            if c.lower() in NO_TRANSLATE_SIGNALS:
                return True

        return False

    @classmethod
    def clean_text(cls, raw: str) -> str:
        """Normalize whitespace in extracted text."""
        return re.sub(r"\s+", " ", raw).strip()

    @classmethod
    def build_docast(cls, html_content: str, doc_id: str) -> DocAST:
        """Parse HTML and produce a structured DocAST with heading breadcrumbs and ordinals."""
        soup = BeautifulSoup(html_content, "lxml")

        # Strip unhelpful non-content tags
        for unwanted in soup(["script", "style", "noscript", "iframe", "svg"]):
            unwanted.decompose()

        # Target main content container if available, fallback to body
        main_container = soup.find("main") or soup.find("article") or soup.find("body") or soup

        root = DocAST.create(kind="root", doc_id=doc_id, ordinal=0)

        current_heading_path: list[str] = []
        current_heading_anchor: str | None = None
        ordinal = 1

        # Walk through top-level block elements
        for element in main_container.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "ul", "ol", "table"],
            recursive=True,
        ):
            tag_name = element.name.lower()
            anchor = element.get("id") or element.get("name")

            # 1. Headings (Update breadcrumbs)
            if tag_name.startswith("h") and tag_name[1].isdigit():
                level = int(tag_name[1])
                heading_text = cls.clean_text(element.get_text())
                if not heading_text:
                    continue

                # Adjust breadcrumbs hierarchy
                while len(current_heading_path) >= level:
                    current_heading_path.pop()
                current_heading_path.append(heading_text)
                current_heading_anchor = anchor

                node = DocAST.create(
                    kind="heading",
                    doc_id=doc_id,
                    ordinal=ordinal,
                    text=heading_text,
                    level=level,
                    anchor=anchor,
                    heading_path=tuple(current_heading_path),
                )
                root.children.append(node)
                ordinal += 1

            # 2. Structural Code Blocks (`pre`)
            elif tag_name == "pre":
                code_text = element.get_text().strip()
                if not code_text:
                    continue

                node = DocAST.create(
                    kind="code_block",
                    doc_id=doc_id,
                    ordinal=ordinal,
                    text=code_text,
                    anchor=anchor or current_heading_anchor,
                    heading_path=tuple(current_heading_path),
                    hard_protected=True,
                )
                root.children.append(node)
                ordinal += 1

            # 3. Paragraphs
            elif tag_name == "p":
                para_text = cls.clean_text(element.get_text())
                if not para_text:
                    continue

                is_hard = cls.is_node_hard_protected(element)
                node = DocAST.create(
                    kind="paragraph",
                    doc_id=doc_id,
                    ordinal=ordinal,
                    text=para_text,
                    anchor=anchor or current_heading_anchor,
                    heading_path=tuple(current_heading_path),
                    hard_protected=is_hard,
                )
                root.children.append(node)
                ordinal += 1

            # 4. Lists (`ul`, `ol`) -> Extract `li` items
            elif tag_name in ("ul", "ol"):
                for li in element.find_all("li", recursive=False):
                    li_text = cls.clean_text(li.get_text())
                    if not li_text:
                        continue
                    node = DocAST.create(
                        kind="list_item",
                        doc_id=doc_id,
                        ordinal=ordinal,
                        text=li_text,
                        heading_path=tuple(current_heading_path),
                    )
                    root.children.append(node)
                    ordinal += 1

        return root
