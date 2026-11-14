"""Invariant property tests: verifying zero-corruption, Merkle proofs, and fail-closed fallback."""

import unittest
from app.core.protection import ProtectedSpan
from app.core.merkle import MerkleTree
from app.core.proof import ProofEngine


class TestPreservationInvariants(unittest.TestCase):
    def setUp(self):
        self.engine = ProofEngine()

    def test_merkle_tree_construction_and_inclusion_proof(self):
        leaf_hashes = [
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "d" * 64,
            "e" * 64,
        ]
        tree = MerkleTree(leaf_hashes)
        root = tree.root
        self.assertIsNotNone(root)
        self.assertEqual(len(root), 64)

        # Verify cryptographic inclusion proof for each leaf
        for leaf in leaf_hashes:
            proof = tree.get_proof(leaf)
            self.assertTrue(MerkleTree.verify_proof(leaf, proof, root))

    def test_successful_preservation_produces_valid_signed_proof(self):
        doc_id = "doc_success_01"
        para_id = "p1"
        orig_para = "Execute pip install fastapi to proceed."
        trans_para = "ಮುಂದುವರಿಯಲು pip install fastapi ಅನ್ನು ಚಲಾಯಿಸಿ."

        span = ProtectedSpan.create(
            doc_id=doc_id,
            para_id=para_id,
            para_ordinal=1,
            span_type="command",
            original="pip install fastapi",
            start=8,
            end=26,
            mode="B",
            detection="rule",
            confidence=0.98,
            sentinel="⟦k1⟧",
        )

        proof, final_paras = self.engine.build_proof(
            doc_id=doc_id,
            target_lang="kn",
            spans=[span],
            translated_paragraphs={para_id: trans_para},
            original_paragraphs={para_id: orig_para},
        )

        self.assertTrue(proof.passed)
        self.assertEqual(proof.failed_count, 0)
        self.assertEqual(len(proof.fallback_paragraphs), 0)
        self.assertEqual(final_paras[para_id], trans_para)

        # Verify cryptographic signature
        self.assertTrue(ProofEngine.verify_signature(proof))

    def test_corrupted_translation_triggers_fail_closed_fallback(self):
        """Invariant: If a model drops or corrupts a command, the paragraph MUST revert to English."""
        doc_id = "doc_corrupt_02"
        para_id = "p2"
        orig_para = "Run docker run -p 8080:80 nginx."
        # Corrupted translation where command was hallucinated/dropped
        corrupted_trans = "ಸರ್ವರ್ ಪ್ರಾರಂಭಿಸಲು ವೆಬ್ ಕಂಟೇನರ್ ಚಲಾಯಿಸಿ."

        span = ProtectedSpan.create(
            doc_id=doc_id,
            para_id=para_id,
            para_ordinal=1,
            span_type="command",
            original="docker run -p 8080:80 nginx",
            start=4,
            end=31,
            mode="B",
            detection="rule",
            confidence=0.99,
            sentinel="⟦k1⟧",
        )

        proof, final_paras = self.engine.build_proof(
            doc_id=doc_id,
            target_lang="kn",
            spans=[span],
            translated_paragraphs={para_id: corrupted_trans},
            original_paragraphs={para_id: orig_para},
        )

        # Invariant checks
        self.assertFalse(proof.passed)
        self.assertEqual(proof.failed_count, 1)
        self.assertIn(para_id, proof.fallback_paragraphs)

        # The output paragraph MUST be the original English text (Fail-Closed)
        self.assertEqual(final_paras[para_id], orig_para)

        # Signature remains valid (it certifies the honest audit)
        self.assertTrue(ProofEngine.verify_signature(proof))


if __name__ == "__main__":
    unittest.main()
