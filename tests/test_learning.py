"""Unit tests for the AI Learning Engine (Flashcards, Quizzes, Curriculum DAG)."""

import unittest
from app.core.docast import DocAST
from app.core.learning import CurriculumDAG, LearningEngine
from app.services.extract import DocumentExtractor

SAMPLE_DOC = """
<!DOCTYPE html>
<html>
<body>
    <main>
        <h1 id="sec-start">Getting Started</h1>
        <p>This library allows developers to build async services efficiently.</p>
        <pre><code>pip install open-docs-engine</code></pre>
        <h2 id="sec-config">Configuration Setup</h2>
        <p>Set up your environment variables before running the application.</p>
        <pre><code>export APP_ENV=production</code></pre>
    </main>
</body>
</html>
"""


class TestLearningEngine(unittest.TestCase):
    def setUp(self):
        self.doc = DocumentExtractor.build_docast(SAMPLE_DOC, doc_id="learn_doc_01")

    def test_generate_flashcards(self):
        cards = LearningEngine.generate_flashcards(self.doc, lang="kn")
        self.assertTrue(len(cards) >= 2)
        
        # Verify card attributes
        self.assertTrue(any("pip install" in (c.code_snippet or "") for c in cards))
        self.assertTrue(any("Getting Started" in c.heading for c in cards))

    def test_export_flashcards_formats(self):
        cards = LearningEngine.generate_flashcards(self.doc)
        md_export = LearningEngine.export_flashcards_markdown(cards)
        tsv_export = LearningEngine.export_flashcards_anki_tsv(cards)

        self.assertIn("# Documentation Flashcard Deck", md_export)
        self.assertIn("\t", tsv_export)  # TSV format check

    def test_generate_and_evaluate_quizzes(self):
        quizzes = LearningEngine.generate_quizzes(self.doc)
        self.assertTrue(len(quizzes) >= 1)

        # First quiz should be command verification
        q = quizzes[0]
        self.assertEqual(len(q.options), 4)
        self.assertEqual(q.correct_index, 0)
        self.assertIn("pip install", q.options[q.correct_index])

    def test_curriculum_dag_recommendations(self):
        sections = [
            {"id": "s1", "heading": "Prerequisites", "order_index": 1, "prerequisites": []},
            {"id": "s2", "heading": "Installation", "order_index": 2, "prerequisites": ["s1"]},
            {"id": "s3", "heading": "Advanced Usage", "order_index": 3, "prerequisites": ["s2"]},
        ]
        dag = CurriculumDAG(sections)

        # Initial recommendation should be s1
        next_sec = dag.get_next_recommended_section(completed_ids=set())
        self.assertEqual(next_sec["id"], "s1")

        # After completing s1, next is s2
        next_sec = dag.get_next_recommended_section(completed_ids={"s1"})
        self.assertEqual(next_sec["id"], "s2")

        # After completing all, next is None
        next_sec = dag.get_next_recommended_section(completed_ids={"s1", "s2", "s3"})
        self.assertIsNone(next_sec)

    def test_concept_explainer_modes(self):
        text = "Dependency Injection in FastAPI"
        eli5 = LearningEngine.explain_concept(text, mode="eli5")
        deep = LearningEngine.explain_concept(text, mode="deep_dive")

        self.assertIn("kitchen recipe", eli5)
        self.assertIn("Architecture & Lifecycle", deep)


if __name__ == "__main__":
    unittest.main()
