"""
red_flag_engine_node.py  (Version 6)
---------------------------------------
Config-driven deterministic red flag evaluation.

V6 rules:
    - Loads rules from config/red_flag_rules.json at module load (singleton).
    - No hardcoded medical if/else.
    - No LLM usage.
    - Escalates risk_level only when rule says and current risk is below threshold.
    - Sets urgency deterministically.
    - Sets red_flag_triggered flag.
    - Pure string matching across symptoms + user_input + reasoning_input.
"""

import json
import os
from functools import lru_cache
from typing import List

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("red_flag_engine")

# Risk escalation order (low → high)
_RISK_ORDER = ["routine", "low", "moderate", "high", "critical"]
_RISK_TO_IDX = {r: i for i, r in enumerate(_RISK_ORDER)}

# Compound word expansions mirrored from risk_tool so fused terms ("chestpain",
# "lefthand") match keyword rules even when the symptom extractor fuses words.
_COMPOUND_EXPANSIONS = {
    "chestpain":           "chest pain",
    "chestache":           "chest ache",
    "heartattack":         "heart attack",
    "heartpain":           "heart pain",
    "lefthand":            "left hand",
    "righthand":           "right hand",
    "leftarm":             "left arm",
    "rightarm":            "right arm",
    "jawpain":             "jaw pain",
    "neckpain":            "neck pain",
    "breathingdifficulty": "difficulty breathing",
}


def _expand_compounds(text: str) -> str:
    """Expand fused medical compound words so keyword checks fire correctly."""
    for compound, expanded in _COMPOUND_EXPANSIONS.items():
        text = text.replace(compound, expanded)
    return text


@lru_cache(maxsize=1)
def _load_rules() -> dict:
    """Loads red_flag_rules.json once and caches the result."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "red_flag_rules.json"
    )
    try:
        with open(os.path.normpath(config_path), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("red_flag_rules.json not found or invalid: %s", exc)
        return {"escalation_rules": [], "urgency_map": {}}


def _build_search_text(state: TriageState) -> str:
    """Builds a single lowercase search string from all relevant state fields.

    Includes raw user messages as a fallback so keywords typed directly by
    the user (e.g. 'I think I'm having a heart attack') are always matched,
    even if the symptom extractor fuses or misses them.
    """
    raw_messages = " ".join(
        m.get("content", "") for m in state.get("messages", []) if m.get("role") == "user"
    )
    parts = [
        " ".join(state.get("symptoms", [])),
        state.get("user_input", ""),
        raw_messages,
        state.get("reasoning_input", ""),
        state.get("extracted_text", ""),
    ]
    combined = " ".join(p for p in parts if p).lower()
    return _expand_compounds(combined)


def _determine_urgency(search_text: str, rules: dict) -> str:
    """Checks urgency_map for the highest severity keyword match."""
    urgency_map = rules.get("urgency_map", {})
    # Check in descending severity order
    for urgency in ("critical", "emergency", "urgent", "routine"):
        keywords = urgency_map.get(urgency, [])
        if any(kw.lower() in search_text for kw in keywords):
            return urgency
    return "routine"


def _should_escalate(current: str, target: str, only_if_below: str = "") -> bool:
    """Returns True if target risk is higher than current risk."""
    current_idx = _RISK_TO_IDX.get(current, 0)
    target_idx  = _RISK_TO_IDX.get(target, 0)
    if only_if_below:
        threshold_idx = _RISK_TO_IDX.get(only_if_below, len(_RISK_ORDER))
        if current_idx >= threshold_idx:
            return False
    return target_idx > current_idx


def red_flag_engine_node(state: TriageState) -> TriageState:
    """
    Evaluates all red flag rules against synthesised text from state.

    No LLM calls. Pure deterministic evaluation.

    Args:
        state: Contains symptoms, user_input, reasoning_input, risk_level.

    Returns:
        TriageState: Updated red_flag_triggered, urgency, risk_level (escalated if needed).
    """
    rules = _load_rules()
    escalation_rules: List[dict] = rules.get("escalation_rules", [])
    search_text = _build_search_text(state)

    if not search_text.strip():
        state.setdefault("red_flag_triggered", False)
        state.setdefault("urgency", "routine")
        log_event(logger, "red_flag_skipped", reason="empty_search_text")
        return state

    # FIX #6 — Escalation override: critical symptom clusters force risk=high, urgency=urgent
    _CRITICAL_OVERRIDES = [
        ("chest pain",           "high", "urgent"),
        ("chest ache",           "high", "urgent"),
        ("breathing difficulty", "high", "urgent"),
        ("difficulty breathing", "high", "urgent"),
        ("severe bleeding",      "high", "urgent"),
        ("cannot breathe",       "high", "emergency"),
        ("heart attack",         "high", "emergency"),
        ("severe chronic disease", "high", "emergency"),
    ]
    for keyword, forced_risk, forced_urgency in _CRITICAL_OVERRIDES:
        if keyword in search_text:
            state["risk_level"] = forced_risk
            state["urgency"]    = forced_urgency
            state["red_flag_triggered"] = True
            log_event(logger, "red_flag_critical_override",
                      keyword=keyword, forced_risk=forced_risk, forced_urgency=forced_urgency)
            return state

    current_risk   = state.get("risk_level", "low").lower()
    triggered      = False
    final_urgency  = _determine_urgency(search_text, rules)
    triggered_id   = None

    for rule in escalation_rules:
        match_any: List[str] = rule.get("match_any", [])
        if not any(kw.lower() in search_text for kw in match_any):
            continue

        # Rule matched
        only_if_below = rule.get("only_if_below", "")
        target_risk   = rule.get("set_risk_level", current_risk)
        set_urgency   = rule.get("set_urgency", final_urgency)

        if rule.get("red_flag_triggered", False):
            triggered = True
            triggered_id = rule.get("id")

        if _should_escalate(current_risk, target_risk, only_if_below):
            current_risk  = target_risk
            final_urgency = set_urgency

        # Once we reach critical, no further escalation possible
        if current_risk == "critical":
            break

    state["red_flag_triggered"] = triggered
    state["urgency"]            = final_urgency
    state["risk_level"]         = current_risk

    log_event(logger, "red_flag_evaluated",
              triggered=triggered,
              rule_id=triggered_id,
              urgency=final_urgency,
              risk_level=current_risk)
    return state
