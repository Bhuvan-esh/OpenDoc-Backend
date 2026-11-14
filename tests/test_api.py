"""Integration and contract tests for FastAPI REST routes."""

import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.services.store import store


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_healthz_and_root(self):
        res = self.client.get("/healthz")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok"})

        res_root = self.client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertIn("OpenDocs", res_root.json()["service"])

    def test_proof_pub_and_manifest(self):
        res_pub = self.client.get("/api/proof.pub")
        self.assertEqual(res_pub.status_code, 200)
        self.assertEqual(res_pub.json()["algorithm"], "Ed25519")
        self.assertIn("public_key_b64", res_pub.json())

        res_manifest = self.client.get("/api/models/manifest")
        self.assertEqual(res_manifest.status_code, 200)
        self.assertTrue(len(res_manifest.json()["adapters"]) >= 1)

    def test_document_ingestion_and_learning_flow(self):
        # 1. Ingest document
        ingest_res = self.client.post("/api/documents", json={"url": "mock://docs.example.com/guide"})
        self.assertEqual(ingest_res.status_code, 202)
        doc_id = ingest_res.json()["doc_id"]
        job_id = ingest_res.json()["job_id"]

        # Verify job was accepted
        self.assertIsNotNone(doc_id)
        self.assertIsNotNone(job_id)

        # 2. Check aligned content
        content_res = self.client.get(f"/api/documents/{doc_id}/content?lang=kn")
        self.assertEqual(content_res.status_code, 200)
        paras = content_res.json()["paragraphs"]
        self.assertTrue(len(paras) >= 1)

        # 3. Check flashcards
        fc_res = self.client.get(f"/api/documents/{doc_id}/flashcards")
        self.assertEqual(fc_res.status_code, 200)
        self.assertTrue(len(fc_res.json()) >= 1)

        # Export flashcards to Anki TSV
        export_res = self.client.get(f"/api/documents/{doc_id}/flashcards/export?format=anki")
        self.assertEqual(export_res.status_code, 200)
        self.assertIn("text/tab-separated-values", export_res.headers["content-type"])

        # 4. Check quizzes and evaluate answer
        quiz_res = self.client.get(f"/api/documents/{doc_id}/quizzes")
        self.assertEqual(quiz_res.status_code, 200)
        quizzes = quiz_res.json()
        self.assertTrue(len(quizzes) >= 1)

        target_quiz = quizzes[0]
        eval_res = self.client.post(
            f"/api/quizzes/{target_quiz['id']}/evaluate",
            json={"selected_index": 0},
        )
        self.assertEqual(eval_res.status_code, 200)
        self.assertTrue(eval_res.json()["is_correct"])

        # 5. Check multi-level explainer
        explain_res = self.client.post(
            f"/api/documents/{doc_id}/explain",
            json={"text": "FastAPI Dependency Injection", "mode": "eli5"},
        )
        self.assertEqual(explain_res.status_code, 200)
        self.assertIn("kitchen recipe", explain_res.json()["explanation"])

        # 6. User progress tracking
        user_token = "tester_123"
        prog_res = self.client.post(
            f"/api/users/{user_token}/progress?doc_id={doc_id}",
            json={"section_id": paras[0]["id"], "status": "completed", "quiz_score": 1.0},
        )
        self.assertEqual(prog_res.status_code, 200)
        self.assertIn(paras[0]["id"], prog_res.json()["completed_sections"])

        # 7. Check signed proof
        proof_res = self.client.get(f"/api/documents/{doc_id}/proof?lang=kn")
        self.assertEqual(proof_res.status_code, 200)
        self.assertTrue(proof_res.json()["passed"])
        self.assertIsNotNone(proof_res.json()["merkle_root"])
        self.assertIsNotNone(proof_res.json()["signature"])

    def test_sandbox_and_diagnostics_endpoints(self):
        # Test code execution
        code_res = self.client.post(
            "/api/sandbox/run",
            json={"language": "python", "code": "print('Test Sandbox API')", "timeout_seconds": 5.0},
        )
        self.assertEqual(code_res.status_code, 200)
        self.assertEqual(code_res.json()["exit_code"], 0)
        self.assertIn("Test Sandbox API", code_res.json()["stdout"])

        # Test error diagnostic endpoint
        err_log = "ModuleNotFoundError: No module named 'fastapi'"
        diag_res = self.client.post(
            "/api/diagnostics/error",
            json={"doc_id": "dummy_doc", "error_log": err_log},
        )
        self.assertEqual(diag_res.status_code, 200)
        self.assertEqual(diag_res.json()["exception_type"], "ModuleNotFoundError")
        self.assertEqual(diag_res.json()["missing_entity"], "fastapi")

    def test_voice_and_qa_and_monitor_endpoints(self):
        # 1. Transcribe audio
        trans_res = self.client.post("/api/speech/transcribe")
        self.assertEqual(trans_res.status_code, 200)
        self.assertIsNotNone(trans_res.json()["text"])

        # 2. TTS synthesis
        tts_res = self.client.post(
            "/api/tts",
            json={"text": "Run pip install to start.", "lang": "kn"},
        )
        self.assertEqual(tts_res.status_code, 200)
        self.assertIsNotNone(tts_res.json()["audio_base64"])
        self.assertTrue(len(tts_res.json()["cue_points"]) >= 1)

        # 3. Monitor register
        mon_res = self.client.post(
            "/api/monitor/register",
            json={"doc_id": "api_doc_test", "url": "mock://api.test", "content_hash": "abc"},
        )
        self.assertEqual(mon_res.status_code, 201)




if __name__ == "__main__":
    unittest.main()
