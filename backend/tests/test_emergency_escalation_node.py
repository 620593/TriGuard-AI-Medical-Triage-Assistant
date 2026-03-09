import pytest
import os
import asyncio
from unittest.mock import patch, MagicMock

from backend.src.nodes.emergency_escalation_node import emergency_escalation_node, _build_voice_summary
from backend.tests.helpers import make_state

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@pytest.fixture
def base_escalation_state():
    return make_state(
        risk_level="high",
        red_flag_triggered=True,
        user_consent_for_call=True,
        emergency_call_triggered=False,
        urgency="emergency",
        symptoms=["chest pain", "shortness of breath"],
        session_id="test-session-123"
    )

def test_build_voice_summary(base_escalation_state):
    summary = _build_voice_summary(base_escalation_state)
    assert "test-session-123" in summary
    assert "HIGH" in summary
    assert "EMERGENCY" in summary
    assert "chest pain, shortness of breath" in summary

def test_emergency_escalation_skipped_already_triggered(base_escalation_state):
    state = base_escalation_state.copy()
    state["emergency_call_triggered"] = True

    with patch("backend.src.nodes.emergency_escalation_node.make_emergency_call") as mock_call:
        result = run(emergency_escalation_node(state))

        mock_call.assert_not_called()
        assert result["emergency_call_triggered"] is True
        assert "call_sid" not in result

def test_emergency_escalation_skipped_risk_low(base_escalation_state):
    state = base_escalation_state.copy()
    state["risk_level"] = "low"

    with patch("backend.src.nodes.emergency_escalation_node.make_emergency_call") as mock_call:
        result = run(emergency_escalation_node(state))

        mock_call.assert_not_called()
        assert result["emergency_call_triggered"] is False

def test_emergency_escalation_skipped_no_red_flag(base_escalation_state):
    state = base_escalation_state.copy()
    state["red_flag_triggered"] = False

    with patch("backend.src.nodes.emergency_escalation_node.make_emergency_call") as mock_call:
        result = run(emergency_escalation_node(state))

        mock_call.assert_not_called()
        assert result["emergency_call_triggered"] is False

def test_emergency_escalation_skipped_auto_disabled(base_escalation_state, monkeypatch):
    monkeypatch.setenv("AUTO_ESCALATION_ENABLED", "false")
    monkeypatch.setenv("EMERGENCY_CONTACT_NUMBER", "+1234567890")

    state = base_escalation_state.copy()

    with patch("backend.src.nodes.emergency_escalation_node.make_emergency_call") as mock_call:
        result = run(emergency_escalation_node(state))

        mock_call.assert_not_called()
        assert result["emergency_call_triggered"] is False

def test_emergency_escalation_skipped_no_consent(base_escalation_state, monkeypatch):
    monkeypatch.setenv("AUTO_ESCALATION_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_CONTACT_NUMBER", "+1234567890")

    state = base_escalation_state.copy()
    state["user_consent_for_call"] = False

    with patch("backend.src.nodes.emergency_escalation_node.make_emergency_call") as mock_call:
        result = run(emergency_escalation_node(state))

        mock_call.assert_not_called()
        assert result["emergency_call_triggered"] is False

def test_emergency_escalation_skipped_no_contact(base_escalation_state, monkeypatch):
    monkeypatch.setenv("AUTO_ESCALATION_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_CONTACT_NUMBER", "")

    state = base_escalation_state.copy()

    with patch("backend.src.nodes.emergency_escalation_node.make_emergency_call") as mock_call:
        result = run(emergency_escalation_node(state))

        mock_call.assert_not_called()
        assert result["emergency_call_triggered"] is False

def test_emergency_escalation_success(base_escalation_state, monkeypatch):
    monkeypatch.setenv("AUTO_ESCALATION_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_CONTACT_NUMBER", "+1234567890")

    state = base_escalation_state.copy()

    with patch("backend.src.nodes.emergency_escalation_node.make_emergency_call") as mock_call:
        mock_call.return_value = {"success": True, "call_sid": "mock_call_sid", "error": None}

        result = run(emergency_escalation_node(state))

        mock_call.assert_called_once()
        args, _ = mock_call.call_args
        assert args[0] == "+1234567890"
        assert "chest pain" in args[1]

        assert result["emergency_call_triggered"] is True
        assert result["call_sid"] == "mock_call_sid"

def test_emergency_escalation_failure(base_escalation_state, monkeypatch):
    monkeypatch.setenv("AUTO_ESCALATION_ENABLED", "true")
    monkeypatch.setenv("EMERGENCY_CONTACT_NUMBER", "+1234567890")

    state = base_escalation_state.copy()

    with patch("backend.src.nodes.emergency_escalation_node.make_emergency_call") as mock_call:
        mock_call.return_value = {"success": False, "call_sid": "", "error": "Twilio Error"}

        result = run(emergency_escalation_node(state))

        mock_call.assert_called_once()
        assert result["emergency_call_triggered"] is False
        assert result.get("call_sid") is None or result.get("call_sid") == ""
