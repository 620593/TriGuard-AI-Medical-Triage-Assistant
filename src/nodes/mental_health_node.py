"""
mental_health_node.py  (NEW — Version 2)
-----------------------------------------
Detects self-harm, suicidal ideation, or hopelessness in user messages.

If a crisis is detected:
  - Sets mental_health_flag = True.
  - Overrides risk_level to 'critical' (or 'high' if already >= high).
  - Sets next_action = 'priority_interrupt' to trigger crisis guidance.

This node runs AFTER risk_evaluation_node so it can override if needed.

Input:
    state (TriageState): Full conversation state.

Returns:
    TriageState: Updated mental_health_flag; possibly overridden risk and next_action.
"""

from src.tools.mental_health_tool import detect_mental_health_crisis
from src.state.state import TriageState


def mental_health_node(state: TriageState) -> TriageState:
    """
    Checks for mental health crisis signals and overrides risk if found.

    Args:
        state (TriageState): Contains messages and current risk assessment.

    Returns:
        TriageState: With mental_health_flag set and risk potentially elevated.
    """
    messages = state.get("messages", [])

    # Run the two-pass mental health crisis detector
    crisis_detected = detect_mental_health_crisis(messages)

    state["mental_health_flag"] = crisis_detected

    if crisis_detected:
        # Override risk — mental health emergencies are always HIGH or CRITICAL
        current_level = state.get("risk_level", "low")
        if current_level not in ("high", "critical"):
            state["risk_level"] = "high"
            state["risk_score"] = max(state.get("risk_score", 0.0), 7.5)

        # Force priority interrupt to deliver crisis guidance immediately
        state["next_action"] = "priority_interrupt"

    return state
