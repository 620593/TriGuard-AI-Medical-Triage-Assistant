"""
emergency_escalation_node.py  (Version 6)
-------------------------------------------
Deterministic emergency phone call via Twilio.

V6 conditions (ALL must be true):
    1. risk_level == "high" (or "critical")
    2. red_flag_triggered == True
    3. AUTO_ESCALATION_ENABLED env var == "true"
    4. user_consent_for_call == True
    5. emergency_call_triggered != True  (deduplication)

V6 rules:
    - No LLM inside this node.
    - Voice summary built deterministically.
    - Uses twilio_client tool (stateless).
    - Stores call_sid for deduplication.
    - Logs escalation event.
"""

import os
import asyncio

from backend.src.state.state import TriageState
from backend.src.tools.twilio_client import make_emergency_call
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("emergency_escalation")

_HIGH_RISK_LEVELS = frozenset({"high", "critical"})


def _has_implied_emergency_consent(state: TriageState) -> bool:
    """Critical voice cases auto-escalate even if the frontend omitted consent."""
    return (
        state.get("input_mode") == "voice"
        and state.get("risk_level", "").lower() == "critical"
        and bool(state.get("red_flag_triggered"))
    )


def _build_call_info(state: TriageState) -> dict:
    """
    Builds a structured info dict for the Twilio emergency call. No LLM.

    Collects all available patient context from state so that
    build_emergency_twiml() (in twilio_client) can produce a rich,
    detailed voice script with symptoms, suspected conditions, and an
    explicit request to dispatch an ambulance.
    """
    return {
        "symptoms":           state.get("symptoms", []),
        "risk_level":         state.get("risk_level", "high"),
        "urgency":            state.get("urgency", "emergency"),
        "disease_candidates": state.get("disease_candidates", []),
        "session_id":         state.get("session_id", "unknown"),
    }


async def emergency_escalation_node(state: TriageState) -> TriageState:
    """
    Places an emergency Twilio call if all conditions are met.

    Args:
        state: Full triage state.

    Returns:
        TriageState: Updated emergency_call_triggered, call_sid.
    """
    # ── Deduplication guard ──────────────────────────────────────────────────
    if state.get("emergency_call_triggered"):
        log_event(logger, "escalation_skipped", reason="already_triggered")
        return state

    # ── Condition checks (all must pass) ─────────────────────────────────────
    risk_level   = state.get("risk_level", "").lower()
    red_flag     = state.get("red_flag_triggered", False)
    explicit_consent = state.get("user_consent_for_call", False)
    auto_enabled = os.getenv("AUTO_ESCALATION_ENABLED", "false").lower() == "true"
    contact      = os.getenv("EMERGENCY_CONTACT_NUMBER", "")

    if risk_level not in _HIGH_RISK_LEVELS:
        log_event(logger, "escalation_skipped", reason="risk_not_high", risk_level=risk_level)
        return state

    if not red_flag:
        log_event(logger, "escalation_skipped", reason="red_flag_not_triggered")
        return state

    if not auto_enabled:
        log_event(logger, "escalation_skipped", reason="auto_escalation_disabled")
        return state

    user_consent = bool(explicit_consent) or _has_implied_emergency_consent(state)
    if not user_consent:
        log_event(logger, "escalation_skipped", reason="user_consent_not_given")
        return state

    if not contact:
        log_event(logger, "escalation_skipped", reason="no_emergency_contact_number")
        return state

    # ── Place the call ────────────────────────────────────────────────────────
    call_info = _build_call_info(state)

    result = await asyncio.to_thread(make_emergency_call, contact, call_info)

    if result["success"]:
        state["emergency_call_triggered"] = True
        state["call_sid"]                 = result["call_sid"]
        log_event(logger, "emergency_call_placed",
                  call_sid=result["call_sid"],
                  risk_level=risk_level,
                  urgency=state.get("urgency", ""))
    else:
        state["emergency_call_triggered"] = False
        log_event(logger, "emergency_call_failed",
                  error=result.get("error", "unknown"),
                  risk_level=risk_level)

    return state
