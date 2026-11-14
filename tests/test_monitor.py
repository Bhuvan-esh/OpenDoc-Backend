"""Unit tests for the Upstream Documentation Monitoring service."""

import asyncio
import unittest
from app.services.extract import DocumentExtractor
from app.services.monitor import UpstreamMonitorService
from app.services.store import store

HTML_V1 = """
<!DOCTYPE html>
<html>
<body>
    <main>
        <h1 id="intro">Project Introduction</h1>
        <p>This is the initial documentation version.</p>
    </main>
</body>
</html>
"""

HTML_V2 = """
<!DOCTYPE html>
<html>
<body>
    <main>
        <h1 id="intro">Project Introduction</h1>
        <p>This is the initial documentation version.</p>
        <h2 id="breaking">Breaking Changes & Migration</h2>
        <p>Follow these steps to upgrade to the next release.</p>
    </main>
</body>
</html>
"""


class TestUpstreamMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = UpstreamMonitorService()
        self.doc_id = "monitored_doc_01"
        self.ast_v1 = DocumentExtractor.build_docast(HTML_V1, doc_id=self.doc_id)
        asyncio.run(store.save_ast(self.doc_id, self.ast_v1))

    def test_unchanged_check(self):
        self.monitor.register_source(
            doc_id=self.doc_id,
            url="http://docs.example.com",
            content_hash="hash_v1",
        )

        diff = asyncio.run(self.monitor.check_for_updates(doc_id=self.doc_id, force_html=HTML_V1))
        # Hash was forced so diff calculated against old_hash
        self.assertTrue(diff.has_changed)
        self.assertEqual(len(diff.added_headings), 0)

    def test_upstream_update_detects_new_sections_and_invalidates_progress(self):
        # Set user progress on this doc
        asyncio.run(
            store.update_user_progress(
                user_token="user_mon",
                doc_id=self.doc_id,
                section_id="intro",
                status="completed",
                score=1.0,
            )
        )

        self.monitor.register_source(
            doc_id=self.doc_id,
            url="http://docs.example.com",
            content_hash="old_initial_hash",
        )

        # Check against HTML_V2 (which adds 'Breaking Changes & Migration')
        diff = asyncio.run(self.monitor.check_for_updates(doc_id=self.doc_id, force_html=HTML_V2))

        self.assertTrue(diff.has_changed)
        self.assertIn("Breaking Changes & Migration", diff.added_headings)
        self.assertTrue(diff.stale_sections_invalidated >= 1)

        # Verify user profile now has stale_sections flagged
        prof = asyncio.run(store.get_user_progress("user_mon", self.doc_id))
        key = f"user_mon:{self.doc_id}"
        self.assertIn("Breaking Changes & Migration", store.user_progress[key]["stale_sections"])


if __name__ == "__main__":
    unittest.main()
