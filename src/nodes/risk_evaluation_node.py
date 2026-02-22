"""
risk_evaluation_node.py  (Version 2)
--------------------------------------
Scores medical risk using the V2 hybrid risk tool (rule-based + LLaMA).

Changes from V1:
  - Stores risk_confidence in state (new V2 field).
  - Logic thresholds adjusted: confidence < 0.6 → ask followup (was 0.7).
  - Critical interrupt requires confidence > 0.85 (unchanged — conservative).

Input:
    state (TriageState): State with symptoms and retrieved_info.

Returns:
    TriageState: Updated with risk_score, risk_level, risk_confidence, next_action.
"""

from src.tools.risk_tool import evaluate_risk
from src.state.state import TriageState

# If confidence below this → don't finalise; ask another follow-up
LOW_CONFIDENCE_THRESHOLD = 0.60

# Only fire priority interrupt at this confidence level (avoid false alarms)
CRITICAL_CONFIDENCE_THRESHOLD = 0.85


def risk_evaluation_node(state: TriageState) -> TriageState:
    """
    Runs hybrid risk evaluation and updates risk fields in state.

    Args:
        state (TriageState): Contains symptoms and retrieved_info.

    Returns:
        TriageState: Updated risk_score, risk_level, risk_confidence, next_action.
    """
    symptoms = state.get("symptoms", [])
    retrieved_info = state.get("retrieved_info", [])
    followup_count = state.get("followup_count", 0)

    # Call the V2 hybrid risk evaluator (plain function, not @tool)
    result = evaluate_risk(
        symptoms=symptoms,
        retrieved_info=retrieved_info,
    )

    # Persist all three risk fields into state
    state["risk_score"] = result["risk_score"]
    state["risk_level"] = result["risk_level"]
    state["risk_confidence"] = result["confidence"]

    confidence = result["confidence"]

    # Low confidence + budget remaining → ask another follow-up
    if confidence < LOW_CONFIDENCE_THRESHOLD and followup_count < 3:
        state["next_action"] = "ask_followup"
        return state

    # Critical + high confidence → trigger emergency alert
    if result["risk_level"] == "critical" and confidence >= CRITICAL_CONFIDENCE_THRESHOLD:
        state["next_action"] = "priority_interrupt"
    else:
        state["next_action"] = ""   # Proceed to mental health check then LLaMA brain

    return state
