"""
whisper_tool.py  (Version 3)
------------------------------
Speech-to-text using Groq's hosted Whisper API.

Why Groq Whisper:
    We already have a Groq API key for LLaMA. Groq hosts Whisper models
    with fast inference, so we reuse the same client — no extra dependency.

Returns:
    dict: { "text": str, "language": str }  — transcribed text + detected language.
"""

import os
from groq import Groq

_client: Groq | None = None


def transcribe_audio(audio_path: str) -> dict:
    """
    Transcribes an audio file using Groq-hosted Whisper.
    Automatically detects the spoken language.

    Args:
        audio_path: Path to audio file (wav, mp3, webm, etc.).

    Returns:
        dict: {"text": transcribed_text, "language": detected_language_code}
              Returns {"text": "", "language": "en"} on failure.
    """
    global _client

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("[whisper_tool] GROQ_API_KEY not set — skipping transcription.")
        return {"text": "", "language": "en"}

    try:
        if _client is None:
            _client = Groq(api_key=api_key)

        with open(audio_path, "rb") as audio_file:
            result = _client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                response_format="verbose_json",
            )

        return {
            "text": result.text.strip() if result.text else "",
            "language": getattr(result, "language", "en") or "en",
        }

    except KeyboardInterrupt:
        print("[whisper_tool] Transcription interrupted.")
        return {"text": "", "language": "en"}

    except Exception as e:
        print(f"[whisper_tool] Transcription failed: {e}")
        return {"text": "", "language": "en"}
