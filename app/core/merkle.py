"""Cryptographic Merkle Tree construction and proof verification."""

from __future__ import annotations

import hashlib


def hash_pair(left: str, right: str) -> str:
    """Hash two hex-encoded hashes together deterministically."""
    combined = (left + right).encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


class MerkleTree:
    """A binary Merkle tree over sorted cryptographic hashes of protected technical spans."""

    def __init__(self, leaf_hashes: list[str]):
        # Sort leaves deterministically
        self.leaves: list[str] = sorted(leaf_hashes)
        self.levels: list[list[str]] = []
        self._build_tree()

    def _build_tree(self) -> None:
        if not self.leaves:
            empty_root = hashlib.sha256(b"EMPTY_TREE").hexdigest()
            self.levels = [[empty_root]]
            return

        current = list(self.leaves)
        self.levels.append(current)

        while len(current) > 1:
            next_level: list[str] = []
            for i in range(0, len(current), 2):
                left = current[i]
                # If odd number of nodes, duplicate the last node
                right = current[i + 1] if i + 1 < len(current) else left
                next_level.append(hash_pair(left, right))
            self.levels.append(next_level)
            current = next_level

    @property
    def root(self) -> str:
        """Return the root hash of the Merkle tree."""
        return self.levels[-1][0]

    def get_proof(self, leaf_hash: str) -> list[dict[str, str]]:
        """Generate an audit path (proof) for a specific leaf hash."""
        if leaf_hash not in self.leaves:
            raise ValueError(f"Leaf {leaf_hash} not present in tree.")

        proof: list[dict[str, str]] = []
        idx = self.leaves.index(leaf_hash)

        for level in self.levels[:-1]:
            is_right = idx % 2 == 1
            sibling_idx = idx - 1 if is_right else idx + 1

            if sibling_idx < len(level):
                sibling_hash = level[sibling_idx]
            else:
                sibling_hash = level[idx]  # Duplicated odd node

            proof.append({
                "position": "left" if is_right else "right",
                "hash": sibling_hash,
            })
            idx //= 2

        return proof

    @classmethod
    def verify_proof(cls, leaf_hash: str, proof: list[dict[str, str]], root: str) -> bool:
        """Verify that a leaf hash belongs to the Merkle tree rooted at `root`."""
        current = leaf_hash
        for step in proof:
            sibling = step["hash"]
            if step["position"] == "left":
                current = hash_pair(sibling, current)
            else:
                current = hash_pair(current, sibling)
        return current == root
