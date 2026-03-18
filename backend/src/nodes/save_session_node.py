"""
save_session_node.py  (Version 5 — Always-Save for In-Session Memory)
----------------------------------------------------------------------
Persists session state to MongoDB after every turn.

V5 Changes (over V4):
    - Removed the `use_history` gate: always save when session_id is present.
      In V4, `use_history=False` caused the save to be skipped, which broke
      in-session memory because load_history_node couldn't find anything.
    - Saves all fields needed for next-turn context restoration:
        messages (last 20), symptoms, last_risk_level, last_intent,
        last_structured_summary, disease_candidates, followup_count.
    - Stateless modes (image, xray, voice) still skip session save — these
      requests produce no persistent conversation state.
    - Fire-and-forget (asyncio.create_task) preserved for non-blocking writes.
"""

import asyncio
from datetime import datetime, timezone

from backend.src.state.state import TriageState
from backend.src.tools.mongodb_tool import update_session, save_report
from backend.src.logging.logger import get_logger, log_event
from backend.src.pipeline_config import STATELESS_INPUT_MODES

logger = get_logger("save_session")

# Fields that must never be persisted to MongoDB
_STRIP_FIELDS = frozenset({
    "image_input", "audio_input", "image_type_hint",
    "_mid_session", "force_accepted", "regeneration_count",
    "vision_findings",    # re-derived each turn
    "session_memory",     # transient — rebuilt every turn by context_synthesizer
    "new_session",        # transient flag
})


async def save_session_node(state: TriageState) -> TriageState:
    """
    Persists session state to MongoDB (when applicable).

    Skips:
        - No session_id (anonymous one-off requests)
        - Stateless modes: image, xray, voice (no conversation continuity)

    Always saves (V5 change):
        - Text-mode turns with a valid session_id, regardless of use_history.
          This is REQUIRED for load_history_node to restore context on the next turn.
    """
    session_id = state.get("session_id", "")

    if not session_id or session_id == "local":
        return state

    # Skip for stateless modes — nothing meaningful to persist
    input_mode = state.get("input_mode", "text")
    if input_mode in STATELESS_INPUT_MODES:
        log_event(logger, "session_save_skipped", reason="stateless_mode", mode=input_mode)
        return state

    # Build minimal vision metadata (no raw data, no findings lists)
    vision_findings = state.get("vision_findings", {})
    vision_metadata = {
        "image_type": vision_findings.get("image_type", "unknown"),
        "confidence": vision_findings.get("confidence", 0.0),
        "visual_findings_count": len(vision_findings.get("visual_findings", []))
    } if vision_findings else {}

    # All fields needed by load_history_node on the next turn
    updates = {
        "messages":               state.get("messages", [])[-20:],   # Rolling 20-message window
        "symptoms":               state.get("symptoms", []),
        "last_symptoms":          state.get("last_symptoms", []) or state.get("symptoms", []),
        "risk_score":             state.get("risk_score", 0.0),
        "risk_level":             state.get("risk_level", ""),
        "last_risk_level":        state.get("risk_level", ""),       # mirror for context_synthesizer
        "last_intent":            state.get("intent", ""),
        "last_structured_summary": state.get("last_structured_summary", ""),
        "disease_candidates":     state.get("disease_candidates", []),
        "followup_count":         state.get("followup_count", 0),
        "language":               state.get("language", "en"),
        "vision_metadata":        vision_metadata,
        "updated_at":             datetime.now(timezone.utc).isoformat(),
    }

    # Fire session update as background task (truly non-blocking)
    try:
        asyncio.create_task(update_session(session_id, updates))
        log_event(logger, "session_update_scheduled",
                  session_id=session_id,
                  message_count=len(updates["messages"]),
                  symptom_count=len(updates["symptoms"]))
    except Exception as e:
        logger.error(f"Failed to schedule session update: {e}")

    # Save summary report in background (only for completed triage — not mid-followup)
    next_action = state.get("next_action", "")
    if next_action not in ("ask_followup",):
        try:
            report_data = {
                "user_id": state.get("user_id"),
                "risk_level": state.get("risk_level", "low"),
                "symptoms": state.get("symptoms", []),
                "image_type": vision_metadata.get("image_type", "none"),
                "confidence": vision_metadata.get("confidence", 0.0),
                "timestamp": state.get("timestamp"),
            }
            asyncio.create_task(save_report(session_id, report_data))
        except Exception as e:
            logger.error(f"Failed to schedule report save: {e}")

    return state
