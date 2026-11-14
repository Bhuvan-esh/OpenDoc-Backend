"""Unit and integration tests for the isolated Code Sandbox runner."""

import asyncio
import unittest
from app.services.sandbox import CodeSandbox


class TestCodeSandbox(unittest.TestCase):
    def test_python_successful_execution(self):
        code = "print('OpenDocs Sandbox Output: 42')"
        result = asyncio.run(CodeSandbox.execute(code, language="python", timeout_seconds=5.0))

        self.assertEqual(result.exit_code, 0)
        self.assertIn("OpenDocs Sandbox Output: 42", result.stdout)
        self.assertFalse(result.timed_out)

    def test_python_runtime_error_captured_in_stderr(self):
        code = "raise RuntimeError('Deliberate sandbox exception')"
        result = asyncio.run(CodeSandbox.execute(code, language="python", timeout_seconds=5.0))

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Deliberate sandbox exception", result.stderr)

    def test_timeout_watchdog_kills_hanging_process(self):
        # Snippet sleeps for 10 seconds, but timeout is capped at 1.0s
        code = "import time\ntime.sleep(10)"
        result = asyncio.run(CodeSandbox.execute(code, language="python", timeout_seconds=1.0))

        self.assertTrue(result.timed_out)
        self.assertEqual(result.exit_code, -1)
        self.assertIn("timed out", result.stderr)


if __name__ == "__main__":
    unittest.main()
