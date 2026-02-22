"""
risk_tool.py  (Version 2)
-------------------------
Context-aware hybrid risk evaluation:
  1. Rule-based red-flag scanner (fast keyword scan).
  2. Multi-flag counting — requires co-occurrence for 'critical'.
  3. LLaMA calibration — adjusts score using retrieved medical context.

Anti-hallucination rules:
  - Never invent disease names.
  - Only uses symptoms + retrieved_info text.
  - If confidence < 0.6 → caller should ask clarification.

Input:
    symptoms      (list[str]): Extracted symptom keywords.
    retrieved_info (list[str]): Tavily medical summaries.

Returns:
    dict: { "risk_score": float, "risk_level": str, "confidence": float }
"""

from backend.src.tools.groq_llama_tool import call_llama

# ── Red-flag keyword sets ─────────────────────────────────────────────────────
# Critical: life-threatening conditions; require ≥2 red flags OR explicit match
_CRITICAL_FLAGS = {
    "cardiac arrest", "heart attack", "stroke", "sepsis", "anaphylaxis",
    "pulmonary embolism", "respiratory failure", "unconscious", "seizure",
    "meningitis", "internal bleeding", "eclampsia",
}

# High: serious but NOT critical alone (e.g., chest pain alone = NOT critical)
_HIGH_FLAGS = {
    "chest pain", "difficulty breathing", "shortness of breath",
    "severe headache", "vomiting blood", "severe dehydration",
    "loss of consciousness", "severe allergic reaction",
}

# Moderate: common concerning symptoms that need medical attention
_MODERATE_FLAGS = {
    "fever", "persistent cough", "abdominal pain", "dizziness", "fatigue",
    "rash", "swelling", "nausea", "diarrhea", "moderate pain",
}

# Benign combos that should NOT escalate risk (anti-hallucination guards)
_BENIGN_COMBOS = [
    {"fever", "cold"},
    {"fever", "runny nose"},
    {"cough", "cold"},
]


def _is_benign_combo(symptom_text: str) -> bool:
    """Returns True if the symptoms match a known benign (low-risk) combination."""
    words = set(symptom_text.lower().split())
    return any(combo.issubset(words) for combo in _BENIGN_COMBOS)


def _rule_based_score(combined: str) -> tuple:
    """
    Fast keyword scan returning (score, level, flag_count).

    Args:
        combined (str): symptoms + retrieved_info joined as one string.

    Returns:
        tuple: (risk_score: float, risk_level: str, flag_count: int)
    """
    text = combined.lower()

    # Count critical red flags present
    critical_hits = sum(1 for f in _CRITICAL_FLAGS if f in text)
    high_hits = sum(1 for f in _HIGH_FLAGS if f in text)
    moderate_hits = sum(1 for f in _MODERATE_FLAGS if f in text)

    # Critical only if ≥2 critical flags OR 1 critical + 1 high (co-occurrence rule)
    if critical_hits >= 2 or (critical_hits >= 1 and high_hits >= 1):
        return 9.5, "critical", critical_hits

    # High: at least one high flag (chest pain alone = not critical)
    if high_hits >= 1:
        # Chest pain alone stays at 7.0, not critical
        return 7.0, "high", high_hits

    if moderate_hits >= 1:
        return 4.5, "moderate", moderate_hits

    return 2.0, "low", 0


def evaluate_risk(symptoms: list, retrieved_info: list) -> dict:
    """
    Hybrid risk scorer: rule-based scan + LLaMA calibration.

    Args:
        symptoms      (list[str]): Patient-reported symptom keywords.
        retrieved_info (list[str]): Tavily medical summaries (max 3).

    Returns:
        dict: {
            "risk_score"  : float (0-10),
            "risk_level"  : str,
            "confidence"  : float (0.0-1.0)
        }
    """
    # Combine all available text
    symptom_text = " ".join(symptoms)
    combined = symptom_text + " " + " ".join(retrieved_info)

    # Guard: known benign combo → force low risk
    if _is_benign_combo(symptom_text):
        return {"risk_score": 2.0, "risk_level": "low", "confidence": 0.85}

    # Step 1: rule-based score
    score, level, flag_count = _rule_based_score(combined)

    # Confidence based on available Tavily context + flag strength
    info_count = len([r for r in retrieved_info if r.strip()])
    base_confidence = min(0.4 + info_count * 0.2, 1.0)  # 0.4 → 0.8

    # Step 2: LLaMA calibration (only when Tavily returned context)
    if info_count > 0:
        context_snippet = " ".join(retrieved_info)[:600]
        prompt = (
            "You are a medical triage assistant. Do NOT diagnose.\n"
            f"Symptoms: {symptom_text}\n"
            f"Medical context: {context_snippet}\n\n"
            "Rate the risk level as exactly ONE of: low, moderate, high, critical.\n"
            "Reply with just the word. No explanation."
        )
        llama_level = call_llama(prompt, max_tokens=10).strip().lower()

        # Accept LLaMA result only if it's a known level
        level_order = ["low", "moderate", "high", "critical"]
        if llama_level in level_order:
            # Blend: take the higher of rule-based vs LLaMA to be safe
            rule_idx = level_order.index(level)
            llama_idx = level_order.index(llama_level)
            final_idx = max(rule_idx, llama_idx)
            level = level_order[final_idx]
            # Map level back to score
            score_map = {"low": 2.0, "moderate": 4.5, "high": 7.0, "critical": 9.5}
            score = score_map[level]
            base_confidence = min(base_confidence + 0.1, 1.0)  # LLaMA agreement boost

    return {
        "risk_score": score,
        "risk_level": level,
        "confidence": round(base_confidence, 2),
    }
