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


def _build_voice_summary(state: TriageState) -> str:
    """Builds a deterministic voice summary for the Twilio call. No LLM."""
    risk_level = state.get("risk_level", "high").upper()
    urgency    = state.get("urgency", "emergency").upper()
    symptoms   = state.get("symptoms", [])
    sym_text   = ", ".join(symptoms[:5]) if symptoms else "reported symptoms"
    session_id = state.get("session_id", "unknown")

    return (
        f"TriGuard AI Medical Alert. A patient with session ID {session_id} "
        f"has been assessed as {risk_level} risk with {urgency} urgency. "
        f"Reported symptoms include: {sym_text}. "
        f"Please ensure the patient receives immediate medical attention. "
        f"This is an automated alert from TriGuard AI triage system."
    )


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
    user_consent = state.get("user_consent_for_call", False)
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

    if not user_consent:
        log_event(logger, "escalation_skipped", reason="user_consent_not_given")
        return state

    if not contact:
        log_event(logger, "escalation_skipped", reason="no_emergency_contact_number")
        return state

    # ── Place the call ────────────────────────────────────────────────────────
    voice_message = _build_voice_summary(state)

    result = await asyncio.to_thread(make_emergency_call, contact, voice_message)

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
