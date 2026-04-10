"""
text_to_speech_node.py  (Version 6)
--------------------------------------
Converts formatted_response to audio when voice_response_required == True.

V6 rules:
    - Uses tts_client tool (stateless).
    - No LLM reasoning inside this node.
    - Only triggers when voice_response_required == True.
    - Writes: audio_path.
"""

import asyncio

from backend.src.state.state import TriageState
from backend.src.tools.tts_client import synthesize_speech
from backend.src.logging.logger import get_logger, log_event
from backend.src.utils.language_utils import normalize_language_code

logger = get_logger("text_to_speech")

# FIX #11 — Symbols and patterns to strip before TTS
import re as _re
_EMOJI_PATTERN = _re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"  # enclosed chars
    "]+",
    flags=_re.UNICODE,
)
_SYMBOL_PATTERN = _re.compile(r"[\u2192\u2022\u26a0\u2714\u2718\u25cf\u2013\u2014\u00b0\u2019\u201c\u201d\u2018#*_`>|~]+")
_MARKDOWN_PATTERN = _re.compile(r"\*{1,3}([^*]+)\*{1,3}")  # bold/italic


def _clean_for_tts(text: str) -> str:
    """FIX #11 — Strip emojis, symbols, and markdown for natural TTS output."""
    # Remove markdown bold/italic
    text = _MARKDOWN_PATTERN.sub(r"\1", text)
    # Remove emojis
    text = _EMOJI_PATTERN.sub(" ", text)
    # Remove arrows, bullets, warning signs, other symbols
    text = _SYMBOL_PATTERN.sub(" ", text)
    # Replace common markdown/text noise
    text = text.replace("\u2192", " to ")  # →
    text = text.replace("\u2022", ".")       # •
    text = text.replace("\u26a0", "Warning:")
    text = text.replace("```", "")
    # Collapse multiple spaces / newlines
    text = _re.sub(r" {2,}", " ", text)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def text_to_speech_node(state: TriageState) -> TriageState:
    """
    Converts the formatted response to audio if voice mode is active.

    Guard: only runs when voice_response_required == True.

    Args:
        state: Contains formatted_response, language, voice_response_required.

    Returns:
        TriageState: audio_path populated on success.
    """
    if not state.get("voice_response_required"):
        log_event(logger, "tts_skipped", reason="voice_not_required")
        return state

    text     = state.get("formatted_response", "") or state.get("final_response", "")
    language = normalize_language_code(state.get("language", "en"))

    if not text.strip():
        log_event(logger, "tts_skipped", reason="no_text_to_synthesize")
        return state

    # FIX #11 — Clean text before TTS: remove emojis, symbols, markdown
    text = _clean_for_tts(text)

    result = await asyncio.to_thread(
        synthesize_speech,
        text=text,
        language=language,
    )

    if result["success"]:
        state["audio_path"] = result["audio_path"]
        # Store the bare filename so routes.py / voice endpoint can build URL
        state["audio_url"] = result.get("audio_filename", "")
        log_event(logger, "tts_completed",
                  audio_path=result["audio_path"],
                  audio_filename=result.get("audio_filename", ""),
                  language=language,
                  text_length=len(text))
    else:
        log_event(logger, "tts_failed",
                  error=result.get("error", "unknown"))

    return state
