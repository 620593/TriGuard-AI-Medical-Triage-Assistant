"""
tts_tool.py  (Version 4 — Production Hardened)
-----------------------------------------------
Text-to-speech output using gTTS (Google Text-to-Speech).

gTTS is free, multilingual, and requires no API key. Produces MP3 output.
Supports 50+ languages — matches our multilingual pipeline.

V4 changes:
    - Removed module-level os.makedirs (directories created by main.py lifespan).
    - Replaced print() with structured logger.
    - Disk cleanup runs before every generation.

Returns:
    str: Filename (not full path) of the generated MP3 audio file, or "" on failure.
"""

import logging
import os
import time
import uuid
from pathlib import Path

from gtts import gTTS

_logger = logging.getLogger("triguard.tts")

# Output directory — anchored to project root, not CWD
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AUDIO_DIR    = str(_PROJECT_ROOT / "audio_output")

_MAX_AGE_SECONDS = 3600  # 1 hour


def _cleanup_old_files() -> None:
    """Deletes audio files older than _MAX_AGE_SECONDS to prevent disk fill."""
    if not os.path.exists(_AUDIO_DIR):
        return
    now = time.time()
    for filename in os.listdir(_AUDIO_DIR):
        filepath = os.path.join(_AUDIO_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            if now - os.path.getmtime(filepath) > _MAX_AGE_SECONDS:
                os.remove(filepath)
        except OSError as exc:
            _logger.warning(f"Audio cleanup failed for {filename}: {exc}")


def text_to_speech(text: str, language: str = "en") -> str:
    """
    Converts text to speech and saves as an MP3 file.

    Args:
        text:     The text to synthesise.
        language: ISO 639-1 language code (default 'en').

    Returns:
        str: Filename of the saved MP3 (e.g. "triage_a1b2c3d4.mp3").
             Empty string on failure.
    """
    if not text or not text.strip():
        return ""

    try:
        # Ensure directory exists (lifespan creates it, but guard defensively)
        os.makedirs(_AUDIO_DIR, exist_ok=True)
        _cleanup_old_files()

        tts      = gTTS(text=text, lang=language, slow=False)
        filename = f"triage_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join(_AUDIO_DIR, filename)
        tts.save(filepath)
        return filename

    except Exception as exc:
        _logger.error(f"TTS generation failed: {exc}")
        return ""
