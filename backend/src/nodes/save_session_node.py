"""
save_session_node.py  (Version 4 — Lightweight)
-----------------------------------------------
Persists session state metadata to MongoDB.

V4 changes:
    - Stateless modes (image, xray, voice) skip session save entirely.
      These requests produce no cross-session continuity state.
    - Report saving is skipped when use_history=False (default).
    - MongoDB update is fire-and-forget (does not block the response).
    - Only minimal metadata is persisted to keep writes fast.
"""

import asyncio
from backend.src.state.state import TriageState
from backend.src.tools.mongodb_tool import update_session, save_report
from backend.src.logging.logger import get_logger, log_event
from backend.src.pipeline_config import STATELESS_INPUT_MODES

logger = get_logger("save_session")


async def save_session_node(state: TriageState) -> TriageState:
    """
    Persists minimal session metadata to MongoDB (when applicable).

    Args:
        state: Fully updated pipeline state.

    Returns:
        TriageState: Unchanged (side-effect is DB write only).
    """
    session_id = state.get("session_id", "")

    if not session_id or session_id == "local":
        return state

    # Skip for stateless modes — nothing meaningful to persist
    input_mode = state.get("input_mode", "text")
    if input_mode in STATELESS_INPUT_MODES:
        log_event(logger, "session_save_skipped", reason="stateless_mode", mode=input_mode)
        return state

    # Skip when history is not being tracked for this session
    if not state.get("use_history", False):
        log_event(logger, "session_save_skipped", reason="use_history_not_set")
        return state

    # Build minimal vision metadata (no raw data, no findings lists)
    vision_findings = state.get("vision_findings", {})
    vision_metadata = {
        "image_type": vision_findings.get("image_type", "unknown"),
        "confidence": vision_findings.get("confidence", 0.0),
        "visual_findings_count": len(vision_findings.get("visual_findings", []))
    } if vision_findings else {}

    updates = {
        "messages": state.get("messages", [])[-20:],   # Cap to 20 (reduced from 50)
        "symptoms": state.get("symptoms", []),
        "risk_score": state.get("risk_score", 0.0),
        "risk_level": state.get("risk_level", ""),
        "language": state.get("language", "en"),
        "vision_metadata": vision_metadata,
    }

    # Fire session update as background task (truly non-blocking)
    # Using create_task means we don't await the DB write —
    # the graph node returns immediately and the write happens concurrently.
    try:
        asyncio.create_task(update_session(session_id, updates))
    except Exception as e:
        logger.error(f"Failed to schedule session update: {e}")

    # Save summary report in background (only for completed triage)
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
