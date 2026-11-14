"""Translation model router and adapter registry."""

from __future__ import annotations

import time
from typing import Any
from app.adapters.base import TranslationResult, TranslatorAdapter

# Curated high-frequency glossary mappings for Kannada, Hindi, and German
DEMO_DICTIONARY = {
    "kn": {
        "introduction": "ಪರಿಚಯ",
        "installation": "ಅನುಸ್ಥಾಪನೆ",
        "prerequisites": "ಪೂರ್ವಾಪೇಕ್ಷಿತಗಳು",
        "quickstart": "ತ್ವರಿತ ಆರಂಭ",
        "to install with standard dependencies": "ಪ್ರಮಾಣಿತ ಅವಲಂಬನೆಗಳೊಂದಿಗೆ ಸ್ಥಾಪಿಸಲು",
        "run the following command": "ಕೆಳಗಿನ ಆಜ್ಞೆಯನ್ನು ಚಲಾಯಿಸಿ",
        "requires python": "ಪೈಥಾನ್ ಅಗತ್ಯವಿದೆ",
        "runs on uvicorn asgi server": "Uvicorn ASGI ಸರ್ವರ್‌ನಲ್ಲಿ ಚಲಿಸುತ್ತದೆ",
        "is a modern web framework for python": "ಪೈಥಾನ್‌ಗಾಗಿ ಆಧುನಿಕ ವೆಬ್ ಫ್ರೇಮ್‌ವರ್ಕ್ ಆಗಿದೆ",
        "to start the server": "ಸರ್ವರ್ ಅನ್ನು ಪ್ರಾರಂಭಿಸಲು",
        "configuration": "ಸಂರಚನೆ",
        "execute the following": "ಕೆಳಗಿನವುಗಳನ್ನು ಕಾರ್ಯಗತಗೊಳಿಸಿ",
    },
    "hi": {
        "introduction": "परिचय",
        "installation": "स्थापना",
        "prerequisites": "पूर्वापेक्षाएँ",
        "quickstart": "त्वरित शुरुआत",
        "to install with standard dependencies": "मानक निर्भरताओं के साथ स्थापित करने के लिए",
        "run the following command": "निम्न कमांड चलाएँ",
        "requires python": "पायथन की आवश्यकता है",
        "runs on uvicorn asgi server": "Uvicorn ASGI सर्वर पर चलता है",
        "is a modern web framework for python": "पायथन के लिए एक आधुनिक वेब ढाँचा है",
        "to start the server": "सर्वर शुरू करने के लिए",
        "configuration": "विन्यास",
        "execute the following": "निम्नलिखित निष्पादित करें",
    },
    "de": {
        "introduction": "Einführung",
        "installation": "Installation",
        "prerequisites": "Voraussetzungen",
        "quickstart": "Schnellstart",
        "to install with standard dependencies": "Für die Installation mit Standard-Abhängigkeiten",
        "run the following command": "führen Sie folgenden Befehl aus",
        "requires python": "erfordert Python",
        "runs on uvicorn asgi server": "läuft auf dem Uvicorn ASGI-Server",
        "is a modern web framework for python": "ist ein modernes Web-Framework für Python",
        "to start the server": "um den Server zu starten",
        "configuration": "Konfiguration",
        "execute the following": "führen Sie Folgendes aus",
    },
}


class MockTranslatorAdapter:
    """High-assurance deterministic translator preserving Mode B sentinels for demo & CI."""

    id = "mock-indic-v1"
    model_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    license = "Apache-2.0"
    origin = "mock"

    def supports(self, src: str, tgt: str) -> bool:
        return src == "en" and tgt in ("kn", "hi", "de", "ar")

    async def translate_batch(
        self,
        texts: list[str],
        src: str,
        tgt: str,
        context: list[str] | None = None,
    ) -> TranslationResult:
        start = time.perf_counter()
        translated: list[str] = []
        glossary = DEMO_DICTIONARY.get(tgt, {})

        for text in texts:
            trans = text
            # Replace known English phrases with target language phrases while keeping sentinels untouched
            for en_term, tgt_term in glossary.items():
                if en_term.lower() in trans.lower():
                    # Case-insensitive replacement
                    idx = trans.lower().find(en_term.lower())
                    trans = trans[:idx] + tgt_term + trans[idx + len(en_term):]

            # If no term matched, prepend target-language descriptor
            if trans == text:
                prefix = {"kn": "ಕನ್ನಡ ವಿವರಣೆ", "hi": "हिंदी विवरण", "de": "Deutsche Beschreibung"}.get(tgt, "Translated")
                trans = f"{prefix}: {text}"

            translated.append(trans)

        ms = int((time.perf_counter() - start) * 1000)
        return TranslationResult(
            translated_texts=translated,
            adapter_id=self.id,
            model_sha=self.model_sha,
            target_lang=tgt,
            execution_ms=ms,
        )


class AdapterRouter:
    """Selects and provides the optimal translator adapter for a language pair."""

    def __init__(self):
        self.adapters: list[TranslatorAdapter] = [
            MockTranslatorAdapter(),
        ]

    def get_adapter(self, src: str, tgt: str) -> TranslatorAdapter:
        for adapter in self.adapters:
            if adapter.supports(src, tgt):
                return adapter
        raise ValueError(f"No translation adapter available for direction {src} -> {tgt}")

    def get_manifest(self) -> list[dict[str, Any]]:
        """Return the public model manifest detailing architecture, weights, and licenses."""
        return [
            {
                "id": a.id,
                "model_sha256": a.model_sha,
                "license": a.license,
                "origin": a.origin,
                "supported_pairs": ["en->kn", "en->hi", "en->de", "en->ar"],
            }
            for a in self.adapters
        ]
