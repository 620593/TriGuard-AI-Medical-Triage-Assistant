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
def test_critical_voice_case_requires_explicit_consent(mock_getenv, mock_call):
    """Even critical voice cases must not call without explicit user consent."""
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

    assert result.get("emergency_call_triggered") is not True
    mock_call.assert_not_called()


@patch("backend.src.nodes.emergency_escalation_node.make_emergency_call")
@patch("backend.src.nodes.emergency_escalation_node.os.getenv")
def test_informational_query_never_calls_even_with_consent(mock_getenv, mock_call):
    """Educational queries (e.g. what is heart attack) should never trigger ambulance calls."""
    env_map = {
        "AUTO_ESCALATION_ENABLED": "true",
        "EMERGENCY_CONTACT_NUMBER": "+15551234567",
    }
    mock_getenv.side_effect = lambda key, default="": env_map.get(key, default)
    mock_call.return_value = {"success": True, "call_sid": "CA123"}

    state = make_state(
        messages=[{"role": "user", "content": "What is a heart attack?"}],
        input_mode="voice",
        risk_level="high",
        urgency="emergency",
        red_flag_triggered=True,
        user_consent_for_call=True,
        symptoms=["heart attack"],
    )

    from backend.src.nodes.emergency_escalation_node import emergency_escalation_node
    result = run(emergency_escalation_node(state))

    assert result.get("emergency_call_triggered") is not True
    mock_call.assert_not_called()


@patch("backend.src.nodes.emergency_escalation_node.make_emergency_call")
@patch("backend.src.nodes.emergency_escalation_node.os.getenv")
def test_active_first_person_emergency_auto_escalates(mock_getenv, mock_call):
    """Active first-person emergency statements should auto-escalate even without explicit consent."""
    env_map = {
        "AUTO_ESCALATION_ENABLED": "true",
        "EMERGENCY_CONTACT_NUMBER": "+15551234567",
    }
    mock_getenv.side_effect = lambda key, default="": env_map.get(key, default)
    mock_call.return_value = {"success": True, "call_sid": "CA123"}

    state = make_state(
        messages=[{"role": "user", "content": "I'm sufferingg with heart attack"}],
        input_mode="voice",
        risk_level="high",
        urgency="emergency",
        red_flag_triggered=True,
        user_consent_for_call=False,
        symptoms=["heart attack"],
    )

    from backend.src.nodes.emergency_escalation_node import emergency_escalation_node
    result = run(emergency_escalation_node(state))

    assert result["emergency_call_triggered"] is True
    assert result["call_sid"] == "CA123"
    mock_call.assert_called_once()


@patch("backend.src.nodes.emergency_escalation_node.make_emergency_call")
@patch("backend.src.nodes.emergency_escalation_node.os.getenv")
def test_active_severe_chronic_disease_auto_escalates(mock_getenv, mock_call):
    """Active first-person severe chronic disease statement should auto-escalate."""
    env_map = {
        "AUTO_ESCALATION_ENABLED": "true",
        "EMERGENCY_CONTACT_NUMBER": "+15551234567",
    }
    mock_getenv.side_effect = lambda key, default="": env_map.get(key, default)
    mock_call.return_value = {"success": True, "call_sid": "CA123"}

    state = make_state(
        messages=[{"role": "user", "content": "I'm suffering with severe chronic disease"}],
        input_mode="voice",
        risk_level="high",
        urgency="emergency",
        red_flag_triggered=True,
        user_consent_for_call=False,
        symptoms=["severe chronic disease"],
    )

    from backend.src.nodes.emergency_escalation_node import emergency_escalation_node
    result = run(emergency_escalation_node(state))

    assert result["emergency_call_triggered"] is True
    assert result["call_sid"] == "CA123"
    mock_call.assert_called_once()