"""
whisper_tool.py  (Version 4 — Production Hardened)
---------------------------------------------------
Speech-to-text using Groq's hosted Whisper API.

We already have a Groq API key for LLaMA. Groq hosts Whisper models
with fast inference, so we reuse the same client — no extra dependency.

Returns:
    dict: { "text": str, "language": str } — transcribed text + detected language.

V4 changes:
    - Uses structured logger instead of print() for observability.
    - Thread-safe double-checked locking for client singleton.
"""

import logging
import os
import threading

from groq import Groq

_logger = logging.getLogger("triguard.whisper")

_client: Groq | None = None
_lock = threading.Lock()


def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribes an audio file using Groq-hosted Whisper.
    Automatically detects the spoken language.

    Args:
        audio_path: Path to audio file (wav, mp3, webm, etc.).

    Returns:
        dict: {"text": transcribed_text, "language": detected_language_code}
              Returns {"text": "", "language": "en"} on any failure.
    """
    global _client

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        _logger.warning("GROQ_API_KEY not set — skipping transcription.")
        return {"text": "", "language": "en"}

    try:
        # Double-checked locking for thread-safe singleton init
        if _client is None:
            with _lock:
                if _client is None:
                    _client = Groq(api_key=api_key)

        with open(audio_path, "rb") as audio_file:
            result = _client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                response_format="verbose_json",
            )

        return {
            "text":     result.text.strip() if result.text else "",
            "language": getattr(result, "language", "en") or "en",
        }

    except KeyboardInterrupt:
        _logger.warning("Transcription interrupted by KeyboardInterrupt.")
        return {"text": "", "language": "en"}

    except Exception as exc:
        _logger.error(f"Transcription failed: {exc}")
        return {"text": "", "language": "en"}
