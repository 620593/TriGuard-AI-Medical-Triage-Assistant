"""
twilio_client.py  (Version 6 — tools/)
----------------------------------------
Stateless Twilio voice call client.

Rules:
    - NEVER modifies state.
    - Pure function: accepts args, returns result dict.
    - Reads env vars at call time (not import time).
    - Raises on misconfiguration so nodes can handle gracefully.
"""

import os
from typing import Optional


def make_emergency_call(
    to_number: str,
    voice_message: str,
    from_number: Optional[str] = None,
) -> dict:
    """
    Places an outbound Twilio voice call with a TwiML voice message.

    Args:
        to_number:     E.164 format destination number (e.g. '+15551234567').
        voice_message: Plain text to read via Twilio TTS.
        from_number:   Override Twilio sender number (defaults to env var).

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
        # Import lazily — Twilio is optional dependency; fail at call time, not import time
        from twilio.rest import Client  # type: ignore[import]
        from twilio.twiml.voice_response import VoiceResponse  # type: ignore[import]

        twiml = VoiceResponse()
        twiml.say(voice_message, voice="alice", language="en-US")

        client = Client(account_sid, auth_token)
        call = client.calls.create(
            twiml=str(twiml),
            to=to_number,
            from_=sender,
        )
        return {"success": True, "call_sid": call.sid, "error": None}

    except Exception as exc:
        return {"success": False, "call_sid": "", "error": str(exc)}
