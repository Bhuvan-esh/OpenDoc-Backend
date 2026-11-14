#!/usr/bin/env python3
"""Standalone verification script for OpenDocs Preservation Proofs.

Usage:
    python verify.py proof.json
"""

import base64
import json
import sys
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature


def verify_proof_file(file_path: str) -> bool:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reconstruct canonical signing payload
    payload = {
        "doc_id": data["doc_id"],
        "target_lang": data["target_lang"],
        "total_spans": data["total_spans"],
        "merkle_root": data["merkle_root"],
        "passed": data["passed"],
    }
    canonical_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")

    pub_key_bytes = base64.b64decode(data["public_key_b64"])
    sig_bytes = base64.b64decode(data["signature"])

    public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_key_bytes)

    try:
        public_key.verify(sig_bytes, canonical_bytes)
        print(" Cryptographic Signature: VALID")
        print(f" Merkle Root: {data['merkle_root']}")
        print(f" Total Technical Spans: {data['total_spans']}")
        print(f" Failed Spans: {data['failed_count']}")
        print(f" Invariant Status: {'PASSED (Zero Corruption)' if data['passed'] else 'FAILED'}")
        return True
    except InvalidSignature:
        print(" Cryptographic Signature: INVALID! Proof has been altered.")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify.py <proof_file.json>")
        sys.exit(1)

    success = verify_proof_file(sys.argv[1])
    sys.exit(0 if success else 1)
