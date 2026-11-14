"""Unit tests for DocAST extraction, traversal, and serialization."""

import unittest
from app.core.docast import DocAST
from app.services.extract import DocumentExtractor

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>FastAPI Docs</title></head>
<body>
    <main>
        <h1 id="intro">Introduction to FastAPI</h1>
        <p>FastAPI is a modern web framework for Python.</p>
        <h2 id="install">Installation</h2>
        <p>To install with standard dependencies, run the following command:</p>
        <pre><code class="language-bash">pip install "fastapi[standard]"</code></pre>
        <ul>
            <li>Requires Python 3.8+</li>
            <li>Runs on Uvicorn ASGI server</li>
        </ul>
    </main>
</body>
</html>
"""


class TestDocAST(unittest.TestCase):
    def test_docast_construction_from_html(self):
        doc = DocumentExtractor.build_docast(SAMPLE_HTML, doc_id="test_doc_01")
        self.assertEqual(doc.kind, "root")
        self.assertTrue(len(doc.children) >= 5)

        # Check headings
        headings = [n for n in doc.iter_nodes() if n.kind == "heading"]
        self.assertEqual(len(headings), 2)
        self.assertEqual(headings[0].text, "Introduction to FastAPI")
        self.assertEqual(headings[0].anchor, "intro")
        self.assertEqual(headings[1].text, "Installation")
        self.assertEqual(headings[1].anchor, "install")

        # Check code block
        code_blocks = doc.get_code_blocks()
        self.assertEqual(len(code_blocks), 1)
        self.assertIn("pip install", code_blocks[0].text)
        self.assertTrue(code_blocks[0].hard_protected)

        # Check paragraph extraction
        paragraphs = doc.get_paragraphs()
        self.assertTrue(len(paragraphs) >= 2)

    def test_docast_serialization_roundtrip(self):
        doc = DocumentExtractor.build_docast(SAMPLE_HTML, doc_id="test_doc_02")
        doc_dict = doc.to_dict()
        restored = DocAST.from_dict(doc_dict)

        self.assertEqual(doc.node_id, restored.node_id)
        self.assertEqual(len(doc.children), len(restored.children))
        self.assertEqual(doc.full_text(), restored.full_text())


if __name__ == "__main__":
    unittest.main()
