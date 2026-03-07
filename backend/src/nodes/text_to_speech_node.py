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

logger = get_logger("text_to_speech")


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
    language = state.get("language", "en")

    if not text.strip():
        log_event(logger, "tts_skipped", reason="no_text_to_synthesize")
        return state

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
