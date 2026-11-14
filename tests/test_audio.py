"""Unit tests for ASR speech transcription and TTS cue points generation."""

import sys
import unittest

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncio
from app.services.audio import AudioService


def run(coro):
    """Helper: run a coroutine in a fresh event loop to avoid reuse issues."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestAudioService(unittest.TestCase):
    def test_speech_transcription(self):
        sample_audio = b"SAMPLE_AUDIO_BUFFER"
        res = run(AudioService.transcribe(sample_audio, language="en"))

        self.assertIsNotNone(res.text)
        self.assertEqual(res.language, "en")
        self.assertTrue(res.confidence > 0.90)
        self.assertTrue(res.duration_seconds > 0)

    def test_cue_points_generation(self):
        text = "FastAPI is a modern web framework. It runs on Uvicorn ASGI server! You can start coding today."
        cue_points = AudioService.generate_cue_points(text)

        self.assertEqual(len(cue_points), 3)
        self.assertEqual(cue_points[0].text, "FastAPI is a modern web framework.")
        self.assertEqual(cue_points[0].char_start, 0)
        self.assertTrue(cue_points[0].duration_ms > 0)
        self.assertTrue(cue_points[1].start_ms >= cue_points[0].duration_ms)

    def test_tts_synthesis(self):
        text = "Run pip install fastapi to proceed."
        res = run(AudioService.synthesize(text, lang="kn"))

        self.assertEqual(res.format, "audio/wav")
        self.assertIsNotNone(res.audio_base64)
        self.assertTrue(len(res.cue_points) >= 1)
        self.assertTrue(res.duration_ms > 0)


if __name__ == "__main__":
    unittest.main()
