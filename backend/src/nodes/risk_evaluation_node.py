"""
risk_evaluation_node.py  (Version 5 — V5 UPGRADE)
----------------------------------------------------
Scores medical risk using the hybrid risk tool (rule-based + LLaMA).

V4 fixes (preserved):
    - priority_interrupt only fires if BOTH risk_level is 'critical' AND
      confidence >= CRITICAL_CONFIDENCE_THRESHOLD AND risk_score >= 9.0.
    - svm_confidence is used only for follow-up routing; cannot override risk_level.

# 🔥 UPGRADE V5 changes:
    1. Short-circuit for non-scoreable intents:
         - intent == "document" or risk_level == "not_applicable"
           → skip risk scoring, preserve risk_level="not_applicable"
         - risk_level == "unknown" (vision model failed)
           → skip risk scoring, preserve risk_level="unknown"
         - intent == "xray" → skip (xray_analysis_node handles its own risk)
    2. Only evaluate medical risk for: medical_text, medical_report (after OCR),
       body_image, casual.
    3. Structured logging for all skipped paths.
"""

from backend.src.tools.risk_tool import evaluate_risk
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

import asyncio

logger = get_logger("risk_evaluation")

LOW_CONFIDENCE_THRESHOLD    = 0.60
CRITICAL_CONFIDENCE_THRESHOLD = 0.85
CRITICAL_SCORE_THRESHOLD    = 9.0   # score must ALSO be >= this to trigger emergency

# 🔥 UPGRADE V5: Intents that bypass risk scoring entirely
# xray: xray_analysis_node already computes risk
# document: will be re-processed via OCR → medical_text
_SKIP_RISK_INTENTS = frozenset({"xray"})

# 🔥 UPGRADE V5: Sentinel risk_level values that mean "do not score"
_SKIP_RISK_LEVELS = frozenset({"not_applicable", "unknown"})


def _build_risk_symptoms(state: TriageState) -> list[str]:
    """Falls back to raw user text when symptom extraction missed a critical phrase."""
    symptoms = [s for s in state.get("symptoms", []) if s and str(s).strip()]
    if symptoms:
        return symptoms

    fallback_inputs = []
    user_input = state.get("user_input", "")
    if user_input and user_input.strip():
        fallback_inputs.append(user_input.strip())

    raw_user_messages = [
        m.get("content", "").strip()
        for m in state.get("messages", [])
        if m.get("role") == "user" and m.get("content", "").strip()
    ]
    fallback_inputs.extend(raw_user_messages)

    deduped = []
    for candidate in fallback_inputs:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


async def risk_evaluation_node(state: TriageState) -> TriageState:
    """
    Runs hybrid risk evaluation and updates risk fields in state.

    # 🔥 UPGRADE V5:
    Skips scoring for xray (handled upstream), documents (not_applicable),
    and vision-failure states (unknown). All three cases return immediately
    with their sentinel risk_level preserved so llm_brain can respond correctly.

    Args:
        state: Contains symptoms, retrieved_info, intent, risk_level.

    Returns:
        TriageState: Updated risk_score, risk_level, risk_confidence, next_action.
    """
    intent     = state.get("intent", "medical_text")
    risk_level = state.get("risk_level", "").lower()

    # 🔥 UPGRADE V5: Skip scoring for xray intent (handled by xray_analysis_node)
    if intent in _SKIP_RISK_INTENTS:
        log_event(logger, "risk_evaluation_skipped",
                  reason="xray_intent", intent=intent)
        return state

    # 🔥 UPGRADE V5: Skip scoring when risk_level was already set to a sentinel value
    # "not_applicable" = document image → will be handled via OCR → text pipeline
    # "unknown"        = vision model failed → cannot assess risk safely
    if risk_level in _SKIP_RISK_LEVELS:
        log_event(logger, "risk_evaluation_skipped",
                  reason="sentinel_risk_level", risk_level=risk_level)
        state["next_action"] = ""   # no interrupt, no followup — passthrough
        return state

    # ── Standard risk evaluation for: medical_text, medical_report, body_image, casual ──
    symptoms       = _build_risk_symptoms(state)
    retrieved_info = state.get("retrieved_info", [])
    followup_count = state.get("followup_count", 0)

    result = await asyncio.to_thread(
        evaluate_risk, symptoms=symptoms, retrieved_info=retrieved_info
    )

    state["risk_score"]      = result["risk_score"]
    state["risk_level"]      = result["risk_level"]
    state["risk_confidence"] = result["confidence"]

    confidence = result["confidence"]
    risk_level = result["risk_level"]
    risk_score = result["risk_score"]

    log_event(logger, "risk_evaluated",
              risk_score=risk_score,
              risk_level=risk_level,
              confidence=confidence)

    # Low confidence + follow-up budget remaining → ask clarifying question
    if confidence < LOW_CONFIDENCE_THRESHOLD and followup_count < 3:
        state["next_action"] = "ask_followup"
        return state

    # Emergency alert requires ALL THREE conditions to be true:
    #   1. LLM+rule determined level is 'critical'
    #   2. Model confidence is high (>= 0.85)
    #   3. Raw risk score is >= 9.0 (prevents SVM over-scoring from sneaking through)
    is_true_emergency = (
        risk_level == "critical"
        and confidence >= CRITICAL_CONFIDENCE_THRESHOLD
        and risk_score >= CRITICAL_SCORE_THRESHOLD
    )

    state["next_action"] = "priority_interrupt" if is_true_emergency else ""
    return state
