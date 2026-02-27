"""
svm_analysis_node.py
---------------------
Follow-up tracking and confidence modeling using lightweight SVM-style
scoring — NO LLM call.

This node runs after risk_evaluation in the medical text pipeline.
It augments the risk assessment with:
    1. Symptom pattern matching against known high-risk clusters.
    2. Historical follow-up trend analysis.
    3. Confidence calibration based on symptom count and retrieval quality.

Anti-hallucination:
    - Pure rule-based scoring. Zero LLM involvement.
    - All thresholds are configurable constants, not learned on the fly.
"""

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("svm_analysis")

# ── Known high-risk symptom clusters (rule-based, not ML) ────────────────────
_HIGH_RISK_CLUSTERS = [
    {"chest pain", "shortness of breath"},
    {"chest pain", "arm pain"},
    {"severe headache", "vision changes"},
    {"high fever", "stiff neck"},
    {"difficulty breathing", "swelling"},
    {"sudden weakness", "speech difficulty"},
    {"abdominal pain", "vomiting blood"},
    {"fainting", "rapid heartbeat"},
]

# Weights for confidence calibration
_SYMPTOM_COUNT_WEIGHT = 0.15      # Per symptom bonus
_RETRIEVAL_QUALITY_WEIGHT = 0.20  # Bonus if Tavily returned results
_CLUSTER_MATCH_WEIGHT = 0.25      # Bonus if a known cluster is matched
_FOLLOWUP_DECAY = 0.05            # Penalty per follow-up (diminishing info)


def svm_analysis_node(state: TriageState) -> TriageState:
    """
    Augments risk confidence with rule-based pattern analysis.

    Does NOT call any LLM or external API. Pure deterministic scoring.

    Args:
        state: Contains symptoms, retrieved_info, risk_score, risk_confidence,
               followup_count.

    Returns:
        TriageState: Updated svm_confidence, and potentially adjusted
                     risk_confidence.
    """
    symptoms = set(s.lower() for s in state.get("symptoms", []))
    retrieved_info = state.get("retrieved_info", [])
    followup_count = state.get("followup_count", 0)
    base_confidence = state.get("risk_confidence", 0.5)
    risk_score = state.get("risk_score", 0.0)

    # ── 1. Symptom count bonus ──────────────────────────────────────────────
    symptom_bonus = min(len(symptoms) * _SYMPTOM_COUNT_WEIGHT, 0.30)

    # ── 2. Retrieval quality bonus ──────────────────────────────────────────
    retrieval_bonus = _RETRIEVAL_QUALITY_WEIGHT if len(retrieved_info) >= 2 else 0.0

    # ── 3. Cluster matching ─────────────────────────────────────────────────
    cluster_matched = False
    for cluster in _HIGH_RISK_CLUSTERS:
        if cluster.issubset(symptoms):
            cluster_matched = True
            break

    cluster_bonus = _CLUSTER_MATCH_WEIGHT if cluster_matched else 0.0

    # ── 4. Follow-up decay penalty ──────────────────────────────────────────
    followup_penalty = min(followup_count * _FOLLOWUP_DECAY, 0.15)

    # ── 5. Compute SVM-style confidence ─────────────────────────────────────
    svm_confidence = min(
        base_confidence + symptom_bonus + retrieval_bonus + cluster_bonus - followup_penalty,
        1.0
    )
    svm_confidence = max(svm_confidence, 0.0)

    state["svm_confidence"] = round(svm_confidence, 3)

    # ── 6. Risk level escalation if cluster match detected ──────────────────
    if cluster_matched and risk_score < 6.0:
        state["risk_score"] = max(risk_score, 6.0)
        state["risk_level"] = "high"
        log_event(logger, "cluster_escalation",
                  cluster="matched",
                  new_risk_score=state["risk_score"])

    # ── 7. Update risk_confidence with the calibrated value ─────────────────
    # Blend: 60% original + 40% SVM calibration
    blended = round(0.6 * base_confidence + 0.4 * svm_confidence, 3)
    state["risk_confidence"] = blended

    log_event(logger, "svm_analysis_complete",
              svm_confidence=svm_confidence,
              blended_confidence=blended,
              cluster_matched=cluster_matched,
              symptom_count=len(symptoms))

    return state
