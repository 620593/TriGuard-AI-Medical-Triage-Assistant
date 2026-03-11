"""
test_emergency_escalation_node.py
--------------------------------
Tests for emergency auto-escalation safeguards.
"""

import asyncio
from unittest.mock import patch

from backend.tests.helpers import make_state


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@patch("backend.src.nodes.emergency_escalation_node.make_emergency_call")
@patch("backend.src.nodes.emergency_escalation_node.os.getenv")
def test_critical_voice_case_auto_escalates_without_explicit_consent(mock_getenv, mock_call):
    """Critical voice emergencies should not be blocked by a missing consent flag."""
    env_map = {
        "AUTO_ESCALATION_ENABLED": "true",
        "EMERGENCY_CONTACT_NUMBER": "+15551234567",
    }
    mock_getenv.side_effect = lambda key, default="": env_map.get(key, default)
    mock_call.return_value = {"success": True, "call_sid": "CA123"}

    state = make_state(
        input_mode="voice",
        risk_level="critical",
        urgency="critical",
        red_flag_triggered=True,
        user_consent_for_call=False,
        symptoms=["heart attack"],
    )

    from backend.src.nodes.emergency_escalation_node import emergency_escalation_node
    result = run(emergency_escalation_node(state))

    assert result["emergency_call_triggered"] is True
    assert result["call_sid"] == "CA123"
    mock_call.assert_called_once()