"""Zero-trust protection classifier: identifies and isolates technical tokens (Modes A and B)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Literal

SpanType = Literal[
    "code_block",
    "inline_code",
    "command",
    "flag",
    "url",
    "file_path",
    "env_var",
    "package",
    "version",
    "identifier",
    "hash",
    "config_key",
    "api_name",
    "table",
    "math",
]

ProtectionMode = Literal["A", "B"]
DetectionMethod = Literal["dom", "rule", "gazetteer", "guard"]

# Common CLI root tools to detect terminal command lines
CLI_ROOT_COMMANDS = {
    "pip", "pip3", "npm", "npx", "pnpm", "yarn", "git", "docker", "podman",
    "curl", "wget", "make", "cmake", "python", "python3", "cargo", "go", "apt",
    "apt-get", "brew", "kubectl", "helm", "aws", "gcloud", "terraform", "uv",
    "poetry", "conda", "jupyter", "node", "systemctl", "ssh", "tar", "grep"
}

# Known file extensions representing paths/code files
CODE_EXTENSIONS = {
    "py", "ts", "tsx", "js", "jsx", "go", "rs", "yaml", "yml", "toml", "json",
    "md", "sh", "bash", "zsh", "txt", "csv", "pkl", "pt", "onnx", "ipynb",
    "c", "cpp", "h", "java", "html", "css", "sql", "env"
}


@dataclass
class ProtectedSpan:
    """A strictly preserved segment of code, command, path, or identifier."""

    span_id: str
    doc_id: str
    para_id: str
    para_ordinal: int
    span_type: SpanType
    original: str
    start: int
    end: int
    sha256: str
    mode: ProtectionMode
    detection: DetectionMethod
    confidence: float
    sentinel: str | None = None
    sentinel_present_in_log: bool = False

    @classmethod
    def create(
        cls,
        doc_id: str,
        para_id: str,
        para_ordinal: int,
        span_type: SpanType,
        original: str,
        start: int,
        end: int,
        mode: ProtectionMode,
        detection: DetectionMethod,
        confidence: float,
        sentinel: str | None = None,
    ) -> ProtectedSpan:
        original_bytes = original.encode("utf-8")
        sha256_hash = hashlib.sha256(original_bytes).hexdigest()
        seed = f"{doc_id}:{para_id}:{start}:{end}:{sha256_hash}"
        span_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return cls(
            span_id=span_id,
            doc_id=doc_id,
            para_id=para_id,
            para_ordinal=para_ordinal,
            span_type=span_type,
            original=original,
            start=start,
            end=end,
            sha256=sha256_hash,
            mode=mode,
            detection=detection,
            confidence=confidence,
            sentinel=sentinel,
        )


class ProtectionClassifier:
    """Rule-based, gazetteer-backed, and DOM-driven technical span classifier."""

    # Pre-compiled high-confidence regular expressions
    URL_RE = re.compile(r"https?://[^\s<>\"')]+|www\.[^\s<>\"')]+", re.IGNORECASE)
    FLAG_RE = re.compile(r"(?<!\w)(?:--[a-z][\w-]*(=[^\s]+)?|-[a-zA-Z]\b)")
    ENV_VAR_RE = re.compile(r"(?<!\w)(?:\$[A-Z_][A-Z0-9_]*|\$\{[A-Z_][A-Z0-9_]*\}|[A-Z][A-Z0-9_]{2,})(?!\w)")
    VERSION_RE = re.compile(r"(?<!\w)(?:v?\d+\.\d+(?:\.\d+)?(?:-[a-zA-Z0-9.]+)?|(?:\^|~=|>=|<=|>|<|==)\s*\d+\.\d+(?:\.\d+)?)\b")
    HASH_RE = re.compile(r"\b(?:0x[0-9a-fA-F]{4,}|[0-9a-fA-F]{7,40})\b")
    INLINE_CODE_RE = re.compile(r"`([^`]+)`")
    PATH_RE = re.compile(r"(?<!\w)(?:[.~]?/[\w.-]+(?:/[\w.-]+)*|[A-Za-z]:\\[\w.-]+|[\w.-]+\.(?:" + "|".join(CODE_EXTENSIONS) + r"))\b")
    API_METHOD_RE = re.compile(r"\b[a-zA-Z_]\w*\.[a-zA-Z_]\w*(?:\(\))?")

    def __init__(self, gazetteer_packages: set[str] | None = None):
        self.packages = gazetteer_packages or {
            "fastapi", "uvicorn", "pydantic", "httpx", "torch", "tensorflow",
            "numpy", "pandas", "scipy", "scikit-learn", "pytest", "docker",
            "react", "next", "vue", "angular", "express", "flask", "django"
        }

    def classify_text(
        self,
        text: str,
        doc_id: str,
        para_id: str,
        para_ordinal: int,
    ) -> list[ProtectedSpan]:
        """Scan a prose paragraph and extract all protected Mode B spans."""
        candidates: list[dict] = []

        # 1. Backtick Inline Code (highest confidence)
        for match in self.INLINE_CODE_RE.finditer(text):
            candidates.append({
                "type": "inline_code",
                "original": match.group(0),
                "clean": match.group(1),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.99,
                "detection": "rule",
            })

        # 2. URLs
        for match in self.URL_RE.finditer(text):
            candidates.append({
                "type": "url",
                "original": match.group(0),
                "clean": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.99,
                "detection": "rule",
            })

        # 3. CLI Command Lines (e.g., lines or phrases starting with pip, git, etc.)
        for cmd in CLI_ROOT_COMMANDS:
            pattern = re.compile(rf"(?<!\w)({cmd}\s+[\w\-./=:@~]+(?:\s+[\w\-./=:@~]+)*)", re.IGNORECASE)
            for match in pattern.finditer(text):
                candidates.append({
                    "type": "command",
                    "original": match.group(0),
                    "clean": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.98,
                    "detection": "gazetteer",
                })

        # 4. CLI Flags
        for match in self.FLAG_RE.finditer(text):
            candidates.append({
                "type": "flag",
                "original": match.group(0),
                "clean": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.98,
                "detection": "rule",
            })

        # 5. File Paths
        for match in self.PATH_RE.finditer(text):
            candidates.append({
                "type": "file_path",
                "original": match.group(0),
                "clean": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95,
                "detection": "rule",
            })

        # 6. Versions
        for match in self.VERSION_RE.finditer(text):
            candidates.append({
                "type": "version",
                "original": match.group(0),
                "clean": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.95,
                "detection": "rule",
            })

        # 7. Environment Variables
        for match in self.ENV_VAR_RE.finditer(text):
            token = match.group(0)
            if "_" in token or token.startswith("$"):
                candidates.append({
                    "type": "env_var",
                    "original": token,
                    "clean": token,
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.92,
                    "detection": "rule",
                })

        # 8. Known Packages from gazetteer
        for pkg in self.packages:
            pattern = re.compile(rf"(?<!\w){re.escape(pkg)}(?!\w)", re.IGNORECASE)
            for match in pattern.finditer(text):
                candidates.append({
                    "type": "package",
                    "original": match.group(0),
                    "clean": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "confidence": 0.90,
                    "detection": "gazetteer",
                })

        # 9. API Methods
        for match in self.API_METHOD_RE.finditer(text):
            candidates.append({
                "type": "api_name",
                "original": match.group(0),
                "clean": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.88,
                "detection": "rule",
            })

        # 10. Hashes
        for match in self.HASH_RE.finditer(text):
            candidates.append({
                "type": "hash",
                "original": match.group(0),
                "clean": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.99,
                "detection": "rule",
            })

        # Non-overlapping greedy selection (prefer longest spans first)
        candidates.sort(key=lambda c: (c["end"] - c["start"]), reverse=True)
        claimed_indices: set[int] = set()
        chosen: list[dict] = []

        for c in candidates:
            span_indices = set(range(c["start"], c["end"]))
            if not (span_indices & claimed_indices):
                claimed_indices.update(span_indices)
                chosen.append(c)

        # Sort in reading order
        chosen.sort(key=lambda c: c["start"])

        # Build ProtectedSpan objects with atomic sentinels
        spans: list[ProtectedSpan] = []
        for idx, c in enumerate(chosen):
            sentinel = f"⟦k{idx + 1}⟧"
            # Fail-closed policy: anything >= 0.60 confidence is protected
            mode: ProtectionMode = "B"
            spans.append(
                ProtectedSpan.create(
                    doc_id=doc_id,
                    para_id=para_id,
                    para_ordinal=para_ordinal,
                    span_type=c["type"],
                    original=c["original"],
                    start=c["start"],
                    end=c["end"],
                    mode=mode,
                    detection=c["detection"],
                    confidence=c["confidence"],
                    sentinel=sentinel,
                )
            )

        return spans
