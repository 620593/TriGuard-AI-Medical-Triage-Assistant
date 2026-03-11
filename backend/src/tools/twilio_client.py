"""
twilio_client.py  (Version 7 — Rich Emergency TwiML Script)
------------------------------------------------------------
Stateless Twilio voice call client.

V7 upgrade:
    build_emergency_twiml() builds a structured multi-segment TwiML script
    with pauses and a repeated key-facts section so the message is fully
    clear even if the recipient picks up mid-call.

    The TwiML script has four acts:
      1. Urgent opening  — grabs attention immediately
      2. Patient condition — symptoms, risk, suspected conditions
      3. Action request  — explicitly asks recipient to dispatch an ambulance
      4. Repetition      — repeats critical facts for clarity

    make_emergency_call() now accepts a structured info dict instead of a
    flat string so all patient context is available for the script.

Rules (preserved):
    - NEVER modifies state.
    - Pure function: accepts args, returns result dict.
    - Reads env vars at call time (not import time).
"""

import os
from typing import Optional, Dict, Any


def build_emergency_twiml(info: Dict[str, Any]) -> str:
    """
    Builds a rich, structured TwiML voice script for the emergency call.

    Args:
        info: dict with keys:
            symptoms           (list[str]) — extracted patient symptoms
            risk_level         (str)       — 'high' | 'critical'
            urgency            (str)       — 'urgent' | 'emergency' | 'critical'
            disease_candidates (list[str]) — suspected/possible conditions
            session_id         (str)       — reference ID

    Returns:
        str: Complete TwiML XML string ready to pass to Twilio.
    """
    # Lazy import — twilio is optional; fail at call time not import time
    from twilio.twiml.voice_response import VoiceResponse  # type: ignore[import]

    symptoms   = info.get("symptoms", [])
    risk       = info.get("risk_level", "critical").upper()
    urgency    = info.get("urgency", "emergency").upper()
    diseases   = info.get("disease_candidates", [])
    session_id = info.get("session_id", "unknown")

    sym_text     = ", ".join(symptoms[:5])  if symptoms else "multiple serious symptoms"
    disease_text = ", ".join(diseases[:3])  if diseases else "a serious medical condition"

    r = VoiceResponse()

    # ── Act 1: Urgent opening ─────────────────────────────────────────────────
    r.say(
        "URGENT. URGENT. This is an emergency medical alert from TriGuard AI. "
        "A patient requires immediate emergency assistance.",
        voice="alice", language="en-US",
    )
    r.pause(length=1)

    # ── Act 2: Patient condition ──────────────────────────────────────────────
    r.say(
        f"The patient has been assessed as {risk} risk with {urgency} urgency. "
        f"The patient is currently experiencing: {sym_text}. "
        f"The AI triage system suspects the following conditions: {disease_text}.",
        voice="alice", language="en-US",
    )
    r.pause(length=1)

    # ── Act 3: Action request ─────────────────────────────────────────────────
    r.say(
        "Please dispatch an ambulance to this patient immediately. "
        "This patient requires urgent emergency medical services right now. "
        "Please send an ambulance immediately. This is a life-threatening situation.",
        voice="alice", language="en-US",
    )
    r.pause(length=2)

    # ── Act 4: Repeat critical facts for clarity ──────────────────────────────
    r.say(
        "Repeating the critical information. "
        f"Patient symptoms: {sym_text}. "
        f"Risk level: {risk}. "
        f"Suspected condition: {disease_text}. "
        "Please send an ambulance immediately. "
        f"TriGuard AI reference session I D: {session_id}. "
        "This message will now end. Thank you for responding.",
        voice="alice", language="en-US",
    )

    return str(r)


def make_emergency_call(
    to_number: str,
    info: Dict[str, Any],
    from_number: Optional[str] = None,
) -> dict:
    """
    Places an outbound Twilio emergency voice call with a rich TwiML script.

    Args:
        to_number:   E.164 format destination number (e.g. '+15551234567').
        info:        Structured patient info dict (passed to build_emergency_twiml).
        from_number: Override Twilio sender number (defaults to TWILIO_FROM_NUMBER env).

    Returns:
        dict with keys: {'success': bool, 'call_sid': str, 'error': str | None}

    Raises:
        EnvironmentError: If TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN are missing.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
    sender      = from_number or os.getenv("TWILIO_FROM_NUMBER", "")

    if not account_sid or not auth_token:
        raise EnvironmentError(
            "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in environment."
        )
    if not sender:
        raise EnvironmentError(
            "TWILIO_FROM_NUMBER must be set in environment or passed explicitly."
        )

    try:
        from twilio.rest import Client  # type: ignore[import]

        twiml  = build_emergency_twiml(info)
        client = Client(account_sid, auth_token)
        call   = client.calls.create(
            twiml=twiml,
            to=to_number,
            from_=sender,
        )
        return {"success": True, "call_sid": call.sid, "error": None}

    except Exception as exc:
        return {"success": False, "call_sid": "", "error": str(exc)}

