"""
whisper_client.py  (Version 6 — tools/)
-----------------------------------------
Stateless Groq Whisper speech-to-text client.

Rules:
    - NEVER modifies state.
    - Pure function: accepts audio bytes, returns transcription dict.
    - Reads env vars at call time.
"""

import os
from typing import Optional


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    language: Optional[str] = None,
) -> dict:
    """
    Transcribes audio bytes using Groq Whisper API.

    Args:
        audio_bytes: Raw audio file bytes (webm, mp3, wav, m4a supported).
        filename:    Virtual filename to determine MIME type.
        language:    Optional ISO 639-1 language code hint (e.g. 'en', 'hi').

    Returns:
        dict with keys: {'text': str, 'language': str, 'success': bool, 'error': str | None}
    """
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return {"text": "", "language": language or "en", "success": False,
                "error": "GROQ_API_KEY not set"}

    try:
        from groq import Groq  # type: ignore[import]

        client = Groq(api_key=api_key)
        params: dict = {
            "file": (filename, audio_bytes),
            "model": "whisper-large-v3",
            "response_format": "json",
        }
        if language:
            params["language"] = language

        transcription = client.audio.transcriptions.create(**params)
        text = transcription.text.strip()
        detected_lang = getattr(transcription, "language", language or "en")

        return {"text": text, "language": detected_lang, "success": True, "error": None}

    except Exception as exc:
        return {"text": "", "language": language or "en", "success": False, "error": str(exc)}
