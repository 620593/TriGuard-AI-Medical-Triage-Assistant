"""
mental_health_node.py  (Version 3)
------------------------------------
Detects self-harm, suicidal ideation, or hopelessness in user messages.

V3 changes:
    - Structured logging of crisis detection events.
    - Otherwise identical to V2 (critical safety logic — minimal changes).
"""

from backend.src.tools.mental_health_tool import detect_mental_health_crisis
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

import asyncio

logger = get_logger("mental_health")


async def mental_health_node(state: TriageState) -> TriageState:
    """
    Checks for mental health crisis signals and overrides risk if found.

    Args:
        state: Contains messages and current risk assessment.

    Returns:
        TriageState: With mental_health_flag set and risk potentially elevated.
    """
    messages = state.get("messages", [])

    crisis_detected = await asyncio.to_thread(detect_mental_health_crisis, messages)
    state["mental_health_flag"] = crisis_detected

    if crisis_detected:
        current_level = state.get("risk_level", "low")
        if current_level not in ("high", "critical"):
            state["risk_level"] = "high"
            state["risk_score"] = max(state.get("risk_score", 0.0), 7.5)

        state["next_action"] = "priority_interrupt"

        log_event(logger, "mental_health_crisis_detected",
                  escalation_flag=True,
                  risk_override=state["risk_level"])

    return state
