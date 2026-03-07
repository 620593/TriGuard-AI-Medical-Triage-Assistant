"""
speech_to_text_node.py  (Version 6)
--------------------------------------
Converts voice input bytes to text and sets voice_response_required flag.

V6 rules:
    - Uses whisper_client tool (stateless).
    - No LLM reasoning inside this node.
    - Only writes: user_input, voice_response_required, language.
    - If audio_bytes is absent, passes through transparently.
"""

import asyncio

from backend.src.state.state import TriageState
from backend.src.tools.whisper_client import transcribe_audio
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("speech_to_text")


async def speech_to_text_node(state: TriageState) -> TriageState:
    """
    Transcribes audio input and sets state for voice-response mode.

    Args:
        state: Contains image_input (bytes) when input_mode == 'voice'.

    Returns:
        TriageState: user_input populated from transcription;
                     voice_response_required = True.
    """
    # Only process when mode is voice and audio bytes are present
    if state.get("input_mode") != "voice":
        return state

    audio_bytes = state.get("image_input")
    if not audio_bytes:
        # No audio data — pass through, classification handles text fallback
        log_event(logger, "stt_skipped", reason="no_audio_bytes")
        return state

    language = state.get("language", "en")

    result = await asyncio.to_thread(
        transcribe_audio,
        audio_bytes=audio_bytes if isinstance(audio_bytes, bytes) else audio_bytes.encode(),
        filename="audio.webm",
        language=language,
    )

    if result["success"] and result["text"]:
        state["user_input"] = result["text"]
        state["voice_response_required"] = True
        state["language"] = result.get("language", language)
        # Inject into messages so classification_node can see it
        messages = state.get("messages", [])
        messages.append({"role": "user", "content": result["text"]})
        state["messages"] = messages
        log_event(logger, "stt_completed",
                  language=state["language"],
                  text_length=len(result["text"]))
    else:
        log_event(logger, "stt_failed",
                  error=result.get("error", "unknown"),
                  voice_response_required=False)
        state["voice_response_required"] = False

    return state
