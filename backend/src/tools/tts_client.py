"""
tts_client.py  (Version 7 — audio_output directory fix)
---------------------------------------------------------
Stateless text-to-speech client (gTTS).

Rules:
    - NEVER modifies state.
    - Pure function: accepts text, returns audio file path dict.
    - Writes audio file to backend/audio_output/ so the static-file
      mount at /static/audio/ in main.py can serve it to the browser.
      (Previous V6 mistakenly wrote to tempfile.gettempdir() which is
       not in the static mount, causing 404 when browser tried to fetch.)
"""

import os
import uuid
from pathlib import Path
from typing import Optional


# Resolve audio_output dir relative to this file so it works regardless of CWD.
# File layout:  backend/src/tools/tts_client.py
#               backend/audio_output/
_PROJECT_BACKEND = Path(__file__).resolve().parent.parent.parent  # → backend/
_DEFAULT_AUDIO_DIR = _PROJECT_BACKEND / "audio_output"


def synthesize_speech(
    text: str,
    language: str = "en",
    output_dir: Optional[str] = None,
) -> dict:
    """
    Converts text to speech using gTTS and writes to audio_output/.

    Args:
        text:       Text to synthesize (will be truncated at 4096 chars).
        language:   ISO 639-1 language code (default 'en').
        output_dir: Override output directory (default: backend/audio_output/).

    Returns:
        dict with keys: {'audio_path': str, 'audio_filename': str, 'success': bool, 'error': str | None}
        audio_path     — absolute path to the written .mp3 file
        audio_filename — basename only (e.g. "triage_tts_abc123.mp3")
    """
    if not text or not text.strip():
        return {"audio_path": "", "audio_filename": "", "success": False, "error": "Empty text provided"}

    try:
        from gtts import gTTS  # type: ignore[import]

        out_dir = Path(output_dir) if output_dir else _DEFAULT_AUDIO_DIR
        out_dir.mkdir(parents=True, exist_ok=True)

        safe_text = text[:4096]
        tts = gTTS(text=safe_text, lang=language, slow=False)

        filename = f"triage_tts_{uuid.uuid4().hex}.mp3"
        filepath = out_dir / filename

        tts.save(str(filepath))
        return {
            "audio_path": str(filepath),
            "audio_filename": filename,
            "success": True,
            "error": None,
        }

    except Exception as exc:
        return {"audio_path": "", "audio_filename": "", "success": False, "error": str(exc)}
