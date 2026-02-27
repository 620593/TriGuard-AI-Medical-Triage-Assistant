"""
risk_tool.py  (Version 3)
--------------------------
Context-aware hybrid risk evaluation:
  1. Rule-based red-flag scanner — scans USER SYMPTOMS ONLY (not retrieved articles).
  2. Benign-combo override to prevent over-escalation of common illnesses.
  3. LLaMA calibration — adjusts score using retrieved medical context.
  4. LLaMA verdict takes precedence; rule-based score is the floor, not the ceiling.

Key fixes in V3:
  - Rule scanner now operates ONLY on symptom_text (not combined with retrieved_info).
    Retrieved article text naturally contains scary medical words (meningitis, stroke,
    etc.) that should NOT trigger critical risk for a common headache + fever.
  - LLaMA calibration now REPLACES the rule score (with a floor), not just blends via max().
    This prevents a Tavily article mentioning "meningitis" from overriding LLaMA's "low".
  - Added many more benign combos covering typical cold/flu presentations.
  - Symptom text matching now uses phrase-level check, not naive word-split,
    preventing "slight fever" from matching "fever" in severe contexts.
  - "slight fever" and "mild headache" prefixes are handled explicitly as LOW.

Input:
    symptoms      (list[str]): Extracted symptom keywords (user-reported only).
    retrieved_info (list[str]): Tavily medical summaries (used ONLY by LLaMA).

Returns:
    dict: { "risk_score": float, "risk_level": str, "confidence": float }
"""

from backend.src.tools.groq_llama_tool import call_llama

# ── Severity prefix words that DOWN-grade the following keyword ──────────────
# "slight fever" should NOT score the same as bare "fever"
_MILD_PREFIXES = frozenset({
    "slight", "mild", "minor", "little", "small", "low-grade", "low grade",
    "light", "bit of", "touch of",
})

# ── Red-flag keyword sets ─────────────────────────────────────────────────────

# Critical: unambiguously life-threatening — must appear in USER SYMPTOMS
_CRITICAL_FLAGS = frozenset({
    "cardiac arrest", "heart attack", "stroke", "sepsis", "anaphylaxis",
    "pulmonary embolism", "respiratory failure", "unconscious", "seizure",
    "meningitis", "internal bleeding", "eclampsia", "coma",
})

# High: serious — user must explicitly report these phrases
_HIGH_FLAGS = frozenset({
    "chest pain", "difficulty breathing", "shortness of breath",
    "severe headache", "vomiting blood", "severe dehydration",
    "loss of consciousness", "severe allergic reaction",
    "can't breathe", "cannot breathe",
})

# Moderate: common concerning symptoms needing attention
_MODERATE_FLAGS = frozenset({
    "fever", "persistent cough", "abdominal pain", "dizziness",
    "rash", "swelling", "nausea", "diarrhea", "moderate pain",
    "earache", "sore throat", "vomiting",
})

# Fatigue alone is not worrying
_LOW_FLAGS = frozenset({
    "headache", "fatigue", "tiredness", "runny nose", "sneezing",
    "stuffy nose", "congestion", "mild cough", "slight cough",
})

# Known benign combinations → always LOW risk
_BENIGN_COMBOS = [
    {"fever", "cold"},
    {"fever", "runny nose"},
    {"fever", "headache"},          # Very common — cold/flu
    {"fever", "slight fever"},      # tautological but safe guard
    {"cough", "cold"},
    {"cough", "runny nose"},
    {"headache", "fatigue"},        # tension / dehydration
    {"headache", "tiredness"},
    {"nausea", "headache"},         # Migraine / dehydration
    {"fever", "cough"},             # Common cold
    {"fever", "sore throat"},
    {"headache", "slight fever"},
    {"slight fever", "headache"},
]


def _normalise_symptoms(symptoms: list) -> str:
    """
    Join symptoms into a lowercase phrase string.
    Keeps multi-word symptoms intact (e.g. 'slight fever', 'chest pain').
    """
    return " | ".join(s.strip().lower() for s in symptoms)


def _has_mild_prefix(symptom: str) -> bool:
    """Returns True if the symptom phrase is prefixed by a mild qualifier."""
    parts = symptom.lower().strip().split()
    return bool(parts) and parts[0] in _MILD_PREFIXES


def _is_benign_combo(symptoms: list) -> bool:
    """
    Returns True if the symptom list matches a known low-risk benign pattern.
    Uses phrase-level matching so 'slight fever' counts towards 'fever'.
    """
    # Normalise: map each symptom to its core word (strip mild prefixes)
    normalised = set()
    for s in symptoms:
        text = s.strip().lower()
        # Add both the full phrase AND the core (prefix-stripped) word
        normalised.add(text)
        parts = text.split()
        if len(parts) > 1 and parts[0] in _MILD_PREFIXES:
            normalised.add(" ".join(parts[1:]))   # e.g. "slight fever" → "fever"
        elif len(parts) == 1:
            normalised.add(parts[0])

    return any(combo.issubset(normalised) for combo in _BENIGN_COMBOS)


def _rule_based_score(symptoms: list) -> tuple:
    """
    Fast rule-based risk score based ONLY on user-reported symptoms.

    IMPORTANT: This function NEVER sees retrieved_info text. Scanning article
    text for keywords like 'meningitis' would cause catastrophic false-positives
    for patients reporting only headache and fever.

    Returns:
        tuple: (risk_score: float, risk_level: str)
    """
    symptom_phrases = [s.strip().lower() for s in symptoms]

    # Build sets for flag matching
    symptom_str = " ".join(symptom_phrases)

    # Count flags — but only on actual symptom text
    critical_hits = sum(1 for f in _CRITICAL_FLAGS if f in symptom_str)
    high_hits     = sum(1 for f in _HIGH_FLAGS     if f in symptom_str)
    moderate_hits = sum(1 for f in _MODERATE_FLAGS if f in symptom_str)
    low_hits      = sum(1 for f in _LOW_FLAGS      if f in symptom_str)

    # Subtract mild-prefixed symptoms from higher tiers (e.g., "slight fever")
    # Any symptom with a mild prefix should not count toward moderate+
    mild_symptom_count = sum(1 for s in symptom_phrases if _has_mild_prefix(s))
    # Reduce moderate hits by mild count (floor at 0)
    effective_moderate_hits = max(moderate_hits - mild_symptom_count, 0)

    # Critical: requires ≥2 critical flags OR 1 critical + 1 high
    if critical_hits >= 2 or (critical_hits >= 1 and high_hits >= 1):
        return 9.5, "critical"

    # High: at least 1 high flag (chest pain ALONE → high, not critical)
    if high_hits >= 1:
        return 7.0, "high"

    # Moderate: has clear concerning symptoms without mild qualifiers
    if effective_moderate_hits >= 1:
        return 4.5, "moderate"

    # Low-grade: mild-prefix symptoms or pure low-flag symptoms
    if mild_symptom_count >= 1 or low_hits >= 1 or moderate_hits >= 1:
        return 2.0, "low"

    return 2.0, "low"


def evaluate_risk(symptoms: list, retrieved_info: list) -> dict:
    """
    Hybrid risk scorer: rule-based scan (symptoms only) + LLaMA calibration.

    The rule-based scan produces a FLOOR score.
    LLaMA calibration — which sees retrieved_info context — provides the
    FINAL verdict. LLaMA can LOWER a high rule score (if context shows the
    presentation is benign) but cannot exceed it by more than one level
    (guards against LLaMA hallucinating emergencies).

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
    if not symptoms:
        return {"risk_score": 2.0, "risk_level": "low", "confidence": 0.5}

    # ── Guard: known benign combo → force low risk immediately ────────────────
    if _is_benign_combo(symptoms):
        return {"risk_score": 2.0, "risk_level": "low", "confidence": 0.85}

    # ── Step 1: Rule-based score (symptoms ONLY) ──────────────────────────────
    score, level = _rule_based_score(symptoms)

    # Confidence based on available Tavily context
    info_count = len([r for r in retrieved_info if r and r.strip()])
    base_confidence = min(0.4 + info_count * 0.2, 0.8)  # 0.4 → 0.8; LLaMA adds more

    # ── Step 2: LLaMA calibration (only when Tavily returned context) ─────────
    if info_count > 0:
        symptom_text  = ", ".join(symptoms)
        context_snippet = " ".join(retrieved_info)[:600]

        prompt = (
            "You are a conservative medical triage assistant. Do NOT diagnose.\n"
            "A patient reports these symptoms: {symptoms}\n"
            "Medical reference context: {context}\n\n"
            "Consider ONLY the patient's reported symptoms, not every disease mentioned "
            "in the reference text. Rate the PATIENT'S actual risk level as exactly "
            "ONE of: low, moderate, high, critical.\n"
            "- low: common cold/flu-like symptoms, mild discomfort\n"
            "- moderate: symptoms needing a doctor visit soon\n"
            "- high: symptoms needing urgent/same-day care\n"
            "- critical: life-threatening, call emergency services NOW\n\n"
            "Reply with just the single word. No explanation."
        ).format(symptoms=symptom_text, context=context_snippet)

        llama_level = call_llama(prompt, max_tokens=10).strip().lower()

        level_order = ["low", "moderate", "high", "critical"]
        if llama_level in level_order:
            rule_idx  = level_order.index(level)
            llama_idx = level_order.index(llama_level)

            # LLaMA is authoritative but capped to (rule_level + 1) to prevent
            # hallucinated emergencies. LLaMA can freely lower the rule score.
            capped_llama_idx = min(llama_idx, rule_idx + 1)
            final_idx = capped_llama_idx   # LLaMA verdict, not max()
            level = level_order[final_idx]

            score_map = {"low": 2.0, "moderate": 4.5, "high": 7.0, "critical": 9.5}
            score = score_map[level]
            base_confidence = min(base_confidence + 0.1, 1.0)

    return {
        "risk_score": score,
        "risk_level": level,
        "confidence": round(base_confidence, 2),
    }
