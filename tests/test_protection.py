"""Unit tests for the Protection Classifier and Paragraph Segmenter."""

import unittest
from app.core.protection import ProtectionClassifier
from app.core.segment import ParagraphSegmenter


class TestProtectionClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = ProtectionClassifier()

    def test_extracts_cli_commands_and_flags(self):
        text = "Run git clone https://github.com/foo/bar.git --depth 1 to clone the repo."
        spans = self.classifier.classify_text(text, doc_id="d1", para_id="p1", para_ordinal=1)

        span_originals = [s.original for s in spans]
        # Should detect the url, git clone command, or flag
        self.assertTrue(any("git clone" in s or "https://" in s for s in span_originals))
        self.assertTrue(any("--depth 1" in s or "--depth" in s for s in span_originals))

    def test_extracts_inline_code_and_paths(self):
        text = "Update the configuration in `./config/settings.yaml` and set `DEBUG=True`."
        spans = self.classifier.classify_text(text, doc_id="d1", para_id="p2", para_ordinal=2)

        span_originals = [s.original for s in spans]
        self.assertTrue(any("./config/settings.yaml" in s for s in span_originals))
        self.assertTrue(any("`DEBUG=True`" in s for s in span_originals))

    def test_extracts_package_names_and_versions(self):
        text = "This application requires fastapi >=0.115.0 and python 3.11."
        spans = self.classifier.classify_text(text, doc_id="d1", para_id="p3", para_ordinal=3)

        span_originals = [s.original for s in spans]
        self.assertTrue(any("fastapi" in s.lower() for s in span_originals))
        self.assertTrue(any(">=0.115.0" in s or "3.11" in s for s in span_originals))

    def test_segmenter_sentinel_replacement_and_reassembly(self):
        text = "Run pip install fastapi to start."
        spans = self.classifier.classify_text(text, doc_id="d1", para_id="p4", para_ordinal=4)

        sentinel_str = ParagraphSegmenter.to_sentinel_string(text, spans)
        self.assertNotIn("pip install", sentinel_str)
        self.assertIn("⟦k1⟧", sentinel_str)

        # Reassemble simulated Kannada translation
        translated_sentinel = "ಪ್ರಾರಂಭಿಸಲು ⟦k1⟧ ಚಲಾಯಿಸಿ."
        result = ParagraphSegmenter.reassemble_sentinel_string(translated_sentinel, spans)

        self.assertEqual(result.status, "verified_exact")
        self.assertTrue(result.all_sentinels_found)
        self.assertIn("pip install", result.text)


if __name__ == "__main__":
    unittest.main()
