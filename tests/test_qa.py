"""Unit tests for Grounded Q&A, Appendix B abstention, and Command-in-Answer verification."""

import unittest
from app.services.extract import DocumentExtractor
from app.services.qa import GroundedQAService

DOC_HTML = """
<!DOCTYPE html>
<html>
<body>
    <main>
        <h1 id="intro">FastAPI Framework</h1>
        <p>FastAPI is a modern, fast web framework for building APIs with Python.</p>
        <h2 id="installation">Installation</h2>
        <p>To install with standard dependencies, run the terminal command:</p>
        <pre><code class="language-bash">pip install fastapi[standard]</code></pre>
        <h2 id="server">Running the Application</h2>
        <p>Execute uvicorn to start the local development server:</p>
        <pre><code>uvicorn main:app --reload</code></pre>
    </main>
</body>
</html>
"""


class TestGroundedQA(unittest.TestCase):
    def setUp(self):
        self.doc = DocumentExtractor.build_docast(DOC_HTML, doc_id="qa_doc_01")
        self.qa = GroundedQAService()

    def test_grounded_answer_with_citations(self):
        question = "How do I install this framework with standard dependencies?"
        res = self.qa.answer_question(question, doc_ast=self.doc)

        self.assertFalse(res.abstained)
        self.assertTrue(len(res.citations) >= 1)
        self.assertIn("pip install fastapi[standard]", res.answer)
        self.assertIn("Installation", res.citations[0].heading)
        self.assertEqual(res.citations[0].anchor, "installation")

    def test_appendix_b_exact_abstention_rule(self):
        """Invariant: If question asks about content absent from the page, abstain strictly."""
        question = "What is the secret recipe for baking sourdough bread in Paris?"
        res = self.qa.answer_question(question, doc_ast=self.doc)

        self.assertTrue(res.abstained)
        self.assertEqual(len(res.citations), 0)
        # MUST match exact Appendix B specified phrasing
        self.assertEqual(
            res.answer,
            "I could not find this information in the documentation page you provided.",
        )

    def test_command_in_answer_verification_gate(self):
        question = "How do I run the application server?"
        res = self.qa.answer_question(question, doc_ast=self.doc)

        self.assertFalse(res.abstained)
        # Verified commands should contain uvicorn command
        self.assertTrue(any("uvicorn" in cmd for cmd in res.verified_commands))


if __name__ == "__main__":
    unittest.main()
