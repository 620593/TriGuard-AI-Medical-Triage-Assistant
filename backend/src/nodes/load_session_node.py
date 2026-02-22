"""
load_session_node.py  (Version 3)
-----------------------------------
Loads or creates a session from MongoDB at the start of each graph invocation.

Replaces V2's file-based load_history_node with proper database persistence.

Three modes:
    1. New session (no session_id) → create in MongoDB.
    2. Mid-session re-entry (_mid_session=True) → pass through (state already in memory).
    3. Existing session → load from MongoDB and merge into state.
"""

from backend.src.state.state import TriageState
from backend.src.tools.mongodb_tool import create_session, load_session
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("load_session")


async def load_session_node(state: TriageState) -> TriageState:
    """
    Loads or creates a session from MongoDB.

    Args:
        state: Current pipeline state.

    Returns:
        TriageState: State with session_id populated and history merged.
    """

    # Guard: Mid-session loop re-entry — state is already correct
    if state.get("_mid_session", False):
        log_event(logger, "session_passthrough", session_id=state.get("session_id", ""))
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
            "input_mode": state.get("input_mode", "text"),
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
            # Continue without persistence — pipeline still works
            state["session_id"] = "local"

        return state

    # Existing session: load from MongoDB and merge
    try:
        doc = await load_session(session_id)
        if doc and "state" in doc:
            saved = doc["state"]
            # Merge saved state (don't overwrite current messages from this request)
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
