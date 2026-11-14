"""Multimodal audio endpoints: Speech-to-text transcribe and Text-to-speech with cue points."""

from __future__ import annotations

from fastapi import APIRouter, File, Query, UploadFile
from app.models.schemas import TranscribeResponse, TTSRequest, TTSResponse
from app.services.audio import AudioService

router = APIRouter(prefix="/api", tags=["Multimodal Voice & Audio"])


@router.post("/speech/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile | None = None,
    language: str | None = Query(None, description="Optional expected language code"),
):
    """Transcribe uploaded audio buffer to text with confidence scoring."""
    audio_bytes = b""
    if file:
        audio_bytes = await file.read()
    else:
        # Default test buffer if no file provided
        audio_bytes = b"SAMPLE_AUDIO_BUFFER_FOR_TESTING"

    res = await AudioService.transcribe(audio_bytes=audio_bytes, language=language)
    return TranscribeResponse(
        text=res.text,
        language=res.language,
        confidence=res.confidence,
        duration_seconds=res.duration_seconds,
    )


@router.post("/tts", response_model=TTSResponse)
async def synthesize_speech(req: TTSRequest):
    """Synthesize speech audio from text and return synchronized karaoke-style sentence cue points."""
    res = await AudioService.synthesize(text=req.text, lang=req.lang, speed=req.speed)
    return TTSResponse(
        audio_base64=res.audio_base64,
        format=res.format,
        sample_rate=res.sample_rate,
        duration_ms=res.duration_ms,
        cue_points=[c.to_dict() for c in res.cue_points],
    )
