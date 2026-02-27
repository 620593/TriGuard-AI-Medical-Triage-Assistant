"""
load_session_node.py  (Version 4 — Lightweight)
-----------------------------------
Loads or creates a session from MongoDB at the start of each graph invocation.

V4 changes:
    - Stateless modes (image, xray, voice) skip session loading entirely.
      These are single-shot analysis requests with no cross-session continuity.
    - Session load is skipped when use_history=False (the new default).
      This eliminates a full MongoDB round-trip for the majority of requests.
    - New sessions (no session_id) are still created as before for text mode.
"""

from backend.src.state.state import TriageState
from backend.src.tools.mongodb_tool import create_session, load_session
from backend.src.logging.logger import get_logger, log_event
from backend.src.pipeline_config import STATELESS_INPUT_MODES

logger = get_logger("load_session")


async def load_session_node(state: TriageState) -> TriageState:
    """
    Loads or creates a session from MongoDB.

    Args:
        state: Current pipeline state.

    Returns:
        TriageState: State with session_id populated and history merged (when applicable).
    """
    # Guard: Mid-session loop re-entry — state is already correct
    if state.get("_mid_session", False):
        log_event(logger, "session_passthrough", session_id=state.get("session_id", ""))
        return state

    # Guard: Stateless mode — no cross-session continuity needed.
    # Image/xray/voice are single-shot analysis requests; prior context is irrelevant.
    # Skipping the DB read saves ~50–150ms per request.
    input_mode = state.get("input_mode", "text")
    if input_mode in STATELESS_INPUT_MODES:
        log_event(logger, "session_skipped", reason="stateless_mode", mode=input_mode)
        return state

    # Guard: History opt-out (default) — skip expensive DB read when not needed.
    if not state.get("use_history", False):
        log_event(logger, "session_skipped", reason="use_history_not_set")
        return state

    session_id = state.get("session_id", "")

    # New session: create in MongoDB
    if not session_id:
        initial = {
            "messages": state.get("messages", []),
            "symptoms": [],
            "followup_count": 0,
            "risk_score": 0.0,
            "risk_level": "",
            "language": state.get("language", "en"),
            "input_mode": input_mode,
        }
        try:
            session_id = await create_session(
                user_id=state.get("user_id", "anonymous"),
                initial_state=initial,
            )
            state["session_id"] = session_id
            log_event(logger, "session_created", session_id=session_id)
        except Exception as e:
            log_event(logger, "session_create_failed", error=str(e))
            state["session_id"] = "local"

        return state

    # Existing session: load from MongoDB and merge
    try:
        doc = await load_session(session_id)
        if doc and "state" in doc:
            saved = doc["state"]
            state["symptoms"] = saved.get("symptoms", state.get("symptoms", []))
            state["followup_count"] = saved.get("followup_count", 0)
            state["retrieved_info"] = saved.get("retrieved_info", [])
            state["risk_score"] = saved.get("risk_score", 0.0)
            state["risk_level"] = saved.get("risk_level", "")
            state["risk_confidence"] = saved.get("risk_confidence", 0.0)
            state["language"] = saved.get("language", state.get("language", "en"))
            log_event(logger, "session_loaded", session_id=session_id)
        else:
            log_event(logger, "session_not_found", session_id=session_id)
    except Exception as e:
        log_event(logger, "session_load_failed", error=str(e))

    return state
