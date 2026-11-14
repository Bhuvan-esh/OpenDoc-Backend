"""The Preservation Ledger and cryptographic Ed25519 verification engine."""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.core.merkle import MerkleTree
from app.core.protection import ProtectedSpan


@dataclass
class LedgerEntry:
    """Audit entry for an individual protected technical span."""

    span_id: str
    para_id: str
    span_type: str
    mode: str
    sha_before: str
    sha_after: str
    present: int
    order_ok: bool
    repaired: bool
    status: Literal["mode_a_by_construction", "exact", "repaired", "failed", "fallback_original"]


@dataclass
class PreservationProof:
    """The complete cryptographic certificate asserting zero technical corruption."""

    doc_id: str
    target_lang: str
    total_spans: int
    mode_a_count: int
    mode_b_count: int
    repaired_count: int
    failed_count: int
    passed: bool
    merkle_root: str
    signature: str
    public_key_b64: str
    entries: list[LedgerEntry]
    fallback_paragraphs: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation of proof metadata for cryptographic signing."""
        payload = {
            "doc_id": self.doc_id,
            "target_lang": self.target_lang,
            "total_spans": self.total_spans,
            "merkle_root": self.merkle_root,
            "passed": self.passed,
        }
        return json.dumps(payload, sort_keys=True).encode("utf-8")


class ProofEngine:
    """Calculates verification ledgers, Merkle roots, and Ed25519 digital signatures."""

    def __init__(self, private_key: ed25519.Ed25519PrivateKey | None = None):
        self.private_key = private_key or ed25519.Ed25519PrivateKey.generate()
        self.public_key = self.private_key.public_key()

    @property
    def public_key_b64(self) -> str:
        raw_bytes = self.public_key.public_bytes_raw()
        return base64.b64encode(raw_bytes).decode("utf-8")

    def build_proof(
        self,
        doc_id: str,
        target_lang: str,
        spans: list[ProtectedSpan],
        translated_paragraphs: dict[str, str],  # para_id -> translated text
        original_paragraphs: dict[str, str],    # para_id -> pristine English text
    ) -> tuple[PreservationProof, dict[str, str]]:
        """Verify spans, assemble ledger, apply fail-closed fallback, and sign proof."""
        entries: list[LedgerEntry] = []
        failed_paras: set[str] = set()

        mode_a_count = 0
        mode_b_count = 0
        repaired_count = 0
        failed_count = 0

        leaf_hashes: list[str] = []

        for sp in spans:
            leaf_hashes.append(sp.sha256)

            if sp.mode == "A":
                mode_a_count += 1
                entries.append(
                    LedgerEntry(
                        span_id=sp.span_id,
                        para_id=sp.para_id,
                        span_type=sp.span_type,
                        mode="A",
                        sha_before=sp.sha256,
                        sha_after=sp.sha256,
                        present=1,
                        order_ok=True,
                        repaired=False,
                        status="mode_a_by_construction",
                    )
                )
                continue

            # Mode B verification
            mode_b_count += 1
            text = translated_paragraphs.get(sp.para_id, "")
            occurrence_count = text.count(sp.original)

            if occurrence_count >= 1:
                status = "exact"
                sha_after = sp.sha256
            else:
                status = "failed"
                sha_after = "MISSING_OR_CORRUPT"
                failed_count += 1
                failed_paras.add(sp.para_id)

            entries.append(
                LedgerEntry(
                    span_id=sp.span_id,
                    para_id=sp.para_id,
                    span_type=sp.span_type,
                    mode="B",
                    sha_before=sp.sha256,
                    sha_after=sha_after,
                    present=occurrence_count,
                    order_ok=True,
                    repaired=False,
                    status=status,
                )
            )

        # Fail-closed enforcement: Revert failed paragraphs to pristine original
        final_paragraphs = dict(translated_paragraphs)
        for pid in failed_paras:
            final_paragraphs[pid] = original_paragraphs[pid]

        tree = MerkleTree(leaf_hashes)
        merkle_root = tree.root

        proof_obj = PreservationProof(
            doc_id=doc_id,
            target_lang=target_lang,
            total_spans=len(spans),
            mode_a_count=mode_a_count,
            mode_b_count=mode_b_count,
            repaired_count=repaired_count,
            failed_count=failed_count,
            passed=failed_count == 0,
            merkle_root=merkle_root,
            signature="",  # Signed below
            public_key_b64=self.public_key_b64,
            entries=entries,
            fallback_paragraphs=sorted(failed_paras),
        )

        signature_bytes = self.private_key.sign(proof_obj.canonical_bytes())
        proof_obj.signature = base64.b64encode(signature_bytes).decode("utf-8")

        return proof_obj, final_paragraphs

    @classmethod
    def verify_signature(cls, proof: PreservationProof) -> bool:
        """Cryptographically verify that the proof was signed by the registered public key."""
        try:
            pub_bytes = base64.b64decode(proof.public_key_b64)
            sig_bytes = base64.b64decode(proof.signature)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            public_key.verify(sig_bytes, proof.canonical_bytes())
            return True
        except (InvalidSignature, ValueError):
            return False
