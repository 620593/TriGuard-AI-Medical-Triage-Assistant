"""
tts_tool.py  (Version 3)
--------------------------
Text-to-speech output using gTTS (Google Text-to-Speech).

Why gTTS:
    Free, multilingual, no API key needed. Produces MP3 output.
    Supports 50+ languages out of the box — matches our multilingual pipeline.

Returns:
    str: File path to the generated MP3 audio file.
"""

import os
import uuid
from gtts import gTTS

# Output directory — anchored to project root (not CWD)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AUDIO_DIR = os.path.join(_PROJECT_ROOT, "audio_output")
os.makedirs(_AUDIO_DIR, exist_ok=True)


def text_to_speech(text: str, language: str = "en") -> str:
    """
    Converts text to speech and saves as MP3.

    Args:
        text: The text to speak.
        language: ISO 639-1 language code (default 'en').

    Returns:
        str: File path to the saved MP3. Empty string on failure.
    """
    if not text or not text.strip():
        return ""

    try:
        tts = gTTS(text=text, lang=language, slow=False)
        filename = f"triage_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join(_AUDIO_DIR, filename)
        tts.save(filepath)
        return filepath

    except Exception as e:
        print(f"[tts_tool] TTS generation failed: {e}")
        return ""
