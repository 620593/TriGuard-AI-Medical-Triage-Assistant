"""
risk_evaluation_node.py  (Version 3)
--------------------------------------
Scores medical risk using the hybrid risk tool (rule-based + LLaMA).

V3 changes:
    - Structured logging of risk results.
    - Otherwise identical to V2 (well-tuned thresholds).
"""

from backend.src.tools.risk_tool import evaluate_risk
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("risk_evaluation")

LOW_CONFIDENCE_THRESHOLD = 0.60
CRITICAL_CONFIDENCE_THRESHOLD = 0.85


def risk_evaluation_node(state: TriageState) -> TriageState:
    """
    Runs hybrid risk evaluation and updates risk fields in state.

    Args:
        state: Contains symptoms and retrieved_info.

    Returns:
        TriageState: Updated risk_score, risk_level, risk_confidence, next_action.
    """
    symptoms = state.get("symptoms", [])
    retrieved_info = state.get("retrieved_info", [])
    followup_count = state.get("followup_count", 0)

    result = evaluate_risk(symptoms=symptoms, retrieved_info=retrieved_info)

    state["risk_score"] = result["risk_score"]
    state["risk_level"] = result["risk_level"]
    state["risk_confidence"] = result["confidence"]

    confidence = result["confidence"]

    log_event(logger, "risk_evaluated",
              risk_score=result["risk_score"],
              risk_level=result["risk_level"],
              confidence=confidence)

    # Low confidence + budget remaining → ask another follow-up
    if confidence < LOW_CONFIDENCE_THRESHOLD and followup_count < 3:
        state["next_action"] = "ask_followup"
        return state

    # Critical + high confidence → trigger emergency alert
    if result["risk_level"] == "critical" and confidence >= CRITICAL_CONFIDENCE_THRESHOLD:
        state["next_action"] = "priority_interrupt"
    else:
        state["next_action"] = ""

    return state
