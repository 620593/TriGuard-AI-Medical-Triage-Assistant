"""
save_session_node.py  (Version 3)
-----------------------------------
Persists session state to MongoDB after each graph invocation.

Replaces V2's file-based save_history_node with proper database persistence.
Uses atomic $set updates — never overwrites the full document.
"""

from backend.src.state.state import TriageState
from backend.src.tools.mongodb_tool import update_session, save_report, insert_log
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("save_session")


async def save_session_node(state: TriageState) -> TriageState:
    """
    Saves the current session state to MongoDB.
    Creates a report document if the triage is complete.

    Args:
        state: Full pipeline state.

    Returns:
        TriageState: Unchanged (pass-through after saving).
    """
    session_id = state.get("session_id", "")

    # Skip persistence if no session (local/fallback mode)
    if not session_id or session_id == "local":
        return state

    # Cap conversation history to avoid unbounded growth in MongoDB document size
    MAX_HISTORY_MESSAGES = 50
    messages = state.get("messages", [])
    if len(messages) > MAX_HISTORY_MESSAGES:
        messages = messages[-MAX_HISTORY_MESSAGES:]

    # Build atomic update payload (only changed fields)
    updates = {
        "messages": messages,
        "symptoms": state.get("symptoms", []),
        "followup_count": state.get("followup_count", 0),
        "retrieved_info": state.get("retrieved_info", []),
        "risk_score": state.get("risk_score", 0.0),
        "risk_level": state.get("risk_level", ""),
        "risk_confidence": state.get("risk_confidence", 0.0),
        "mental_health_flag": state.get("mental_health_flag", False),
        "language": state.get("language", "en"),
        "next_action": state.get("next_action", ""),
    }

    try:
        await update_session(session_id, updates)
        log_event(logger, "session_saved", session_id=session_id)
    except Exception as e:
        log_event(logger, "session_save_failed", error=str(e))

    # Save a report if triage is complete (not a follow-up)
    next_action = state.get("next_action", "")
    if next_action not in ("ask_followup",):
        try:
            report_data = {
                "symptoms": state.get("symptoms", []),
                "risk_score": state.get("risk_score", 0.0),
                "risk_level": state.get("risk_level", ""),
                "risk_confidence": state.get("risk_confidence", 0.0),
                "mental_health_flag": state.get("mental_health_flag", False),
                "judge_passed": state.get("judge_passed", True),
                "language": state.get("language", "en"),
                "input_mode": state.get("input_mode", "text"),
                "nutrition_advice": state.get("nutrition_advice", ""),
            }
            await save_report(session_id, report_data)
            log_event(logger, "report_saved", session_id=session_id)
        except Exception as e:
            log_event(logger, "report_save_failed", error=str(e))

    # Log the triage event for observability
    try:
        await insert_log("triage_completed", {
            "session_id": session_id,
            "risk_level": state.get("risk_level", ""),
            "risk_score": state.get("risk_score", 0.0),
            "confidence": state.get("risk_confidence", 0.0),
            "mental_health_flag": state.get("mental_health_flag", False),
            "judge_passed": state.get("judge_passed", True),
        })
    except Exception as e:
        log_event(logger, "log_insert_failed", error=str(e))

    return state
