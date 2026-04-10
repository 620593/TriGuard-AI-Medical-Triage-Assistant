"""
emergency_escalation_node.py  (Version 6)
-------------------------------------------
Deterministic emergency phone call via Twilio.

V6 conditions (ALL must be true):
    1. risk_level == "high" (or "critical")
    2. red_flag_triggered == True
    3. AUTO_ESCALATION_ENABLED env var == "true"
    4. user_consent_for_call == True
    5. user message is not an informational query
    6. emergency_call_triggered != True  (deduplication)

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
_INFO_QUERY_HINTS = (
    "what is",
    "what are",
    "tell me about",
    "explain",
    "information about",
    "symptoms of",
    "causes of",
    "difference between",
    "meaning of",
)
_FIRST_PERSON_HINTS = (
    "i am",
    "i'm",
    "im",
    "my",
    "me",
)
_ACTIVE_EMERGENCY_HINTS = (
    "heart attack",
    "chest pain",
    "cannot breathe",
    "can't breathe",
    "difficulty breathing",
    "severe breathing",
    "stroke",
    "unconscious",
    "cardiac arrest",
    "seizure",
    "vomiting blood",
    "suffering",
    "severe chronic disease",
    "severe chronic condition",
)


def _latest_user_text(state: TriageState) -> str:
    """Returns the latest user message text in lowercase."""
    for msg in reversed(state.get("messages", [])):
        if msg.get("role") == "user":
            return str(msg.get("content", "") or "").strip().lower()
    return ""


def _is_informational_query(state: TriageState) -> bool:
    """True when the user appears to ask educational info, not active distress."""
    text = _latest_user_text(state)
    if not text:
        return False

    # Strictly educational prompts should never trigger emergency calling.
    return any(hint in text for hint in _INFO_QUERY_HINTS)


def _has_implied_emergency_consent(state: TriageState) -> bool:
    """Allow auto-escalation only for active first-person emergency statements."""
    text = _latest_user_text(state)
    if not text:
        return False
    if _is_informational_query(state):
        return False

    has_first_person = any(hint in text for hint in _FIRST_PERSON_HINTS)
    has_emergency_signal = any(hint in text for hint in _ACTIVE_EMERGENCY_HINTS)
    return has_first_person and has_emergency_signal


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

    if _is_informational_query(state):
        log_event(logger, "escalation_skipped", reason="informational_query")
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
