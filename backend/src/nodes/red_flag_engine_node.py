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


@lru_cache(maxsize=1)
def _load_rules() -> dict:
    """Loads red_flag_rules.json once, lowercases keywords, and caches the result."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "red_flag_rules.json"
    )
    try:
        with open(os.path.normpath(config_path), "r", encoding="utf-8") as f:
            rules = json.load(f)

            # Pre-lowercase urgency_map keywords
            urgency_map = rules.get("urgency_map", {})
            for urgency, keywords in urgency_map.items():
                urgency_map[urgency] = [kw.lower() for kw in keywords]

            # Pre-lowercase escalation_rules match_any keywords
            for rule in rules.get("escalation_rules", []):
                if "match_any" in rule:
                    rule["match_any"] = [kw.lower() for kw in rule["match_any"]]

            return rules
    except Exception as exc:
        logger.warning("red_flag_rules.json not found or invalid: %s", exc)
        return {"escalation_rules": [], "urgency_map": {}}


def _build_search_text(state: TriageState) -> str:
    """Builds a single lowercase search string from all relevant fields."""
    parts = [
        " ".join(state.get("symptoms", [])),
        state.get("user_input", ""),
        state.get("reasoning_input", ""),
        state.get("extracted_text", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def _determine_urgency(search_text: str, rules: dict) -> str:
    """Checks urgency_map for the highest severity keyword match."""
    urgency_map = rules.get("urgency_map", {})
    # Check in descending severity order
    for urgency in ("critical", "emergency", "urgent", "routine"):
        keywords = urgency_map.get(urgency, [])
        if any(kw in search_text for kw in keywords):
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

    current_risk   = state.get("risk_level", "low").lower()
    triggered      = False
    final_urgency  = _determine_urgency(search_text, rules)
    triggered_id   = None

    for rule in escalation_rules:
        match_any: List[str] = rule.get("match_any", [])
        if not any(kw in search_text for kw in match_any):
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
