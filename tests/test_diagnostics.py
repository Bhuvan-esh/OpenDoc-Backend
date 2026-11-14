"""Unit tests for the grounded Error Diagnostic Engine."""

import unittest
from app.core.docast import DocAST
from app.services.diagnostics import ErrorDiagnosticEngine
from app.services.extract import DocumentExtractor

SAMPLE_DOC_HTML = """
<!DOCTYPE html>
<html>
<body>
    <main>
        <h1 id="sec-install">Installation Guide</h1>
        <p>To use this library, install the required packages:</p>
        <pre><code class="language-bash">pip install fastapi[standard]</code></pre>
        <h2 id="sec-run">Running the App</h2>
        <p>Start the server using:</p>
        <pre><code>uvicorn app.main:app --port 8000</code></pre>
    </main>
</body>
</html>
"""


class TestErrorDiagnostics(unittest.TestCase):
    def setUp(self):
        self.doc = DocumentExtractor.build_docast(SAMPLE_DOC_HTML, doc_id="diag_doc_01")

    def test_diagnose_modulenotfound_matches_doc_command(self):
        error_log = """
Traceback (most recent call last):
  File "main.py", line 1, in <module>
    import fastapi
ModuleNotFoundError: No module named 'fastapi'
"""
        report = ErrorDiagnosticEngine.diagnose(error_log, doc_ast=self.doc)

        self.assertEqual(report.exception_type, "ModuleNotFoundError")
        self.assertEqual(report.missing_entity, "fastapi")
        self.assertIn("pip install fastapi[standard]", report.recommended_fix_command)
        self.assertIn("Installation Guide", report.cited_section)
        self.assertEqual(report.anchor, "sec-install")
        self.assertTrue(report.confidence >= 0.90)

    def test_diagnose_command_not_found(self):
        error_log = "bash: uvicorn: command not found"
        report = ErrorDiagnosticEngine.diagnose(error_log, doc_ast=self.doc)

        self.assertEqual(report.exception_type, "CommandNotFound")
        self.assertEqual(report.missing_entity, "uvicorn")
        self.assertIn("not installed or not available", report.diagnosis)

    def test_diagnose_unmatched_missing_module_fallback(self):
        # Module not present in doc
        error_log = "ModuleNotFoundError: No module named 'some_unrelated_package'"
        report = ErrorDiagnosticEngine.diagnose(error_log, doc_ast=self.doc)

        self.assertEqual(report.exception_type, "ModuleNotFoundError")
        self.assertEqual(report.missing_entity, "some_unrelated_package")
        self.assertEqual(report.recommended_fix_command, "pip install some_unrelated_package")


if __name__ == "__main__":
    unittest.main()
