"""
test_risk_evaluation_node.py
-----------------------------
Tests for risk_evaluation_node: risk scoring, confidence routing, emergency escalation.
"""

import pytest
from unittest.mock import patch
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_EVAL = "backend.src.nodes.risk_evaluation_node.evaluate_risk"


@patch(MOCK_EVAL)
def test_low_risk_sets_state_correctly(mock_eval):
    """Low risk result is stored in state correctly."""
    mock_eval.return_value = {"risk_score": 2.0, "risk_level": "low", "confidence": 0.85}
    state = make_state(symptoms=["mild headache"])

    from backend.src.nodes.risk_evaluation_node import risk_evaluation_node
    result = run(risk_evaluation_node(state))

    assert result["risk_level"] == "low"
    assert result["risk_score"] == 2.0
    assert result["risk_confidence"] == 0.85
    assert result["next_action"] == ""


@patch(MOCK_EVAL)
def test_low_confidence_triggers_followup(mock_eval):
    """Low confidence + followup budget remaining → ask_followup."""
    mock_eval.return_value = {"risk_score": 4.0, "risk_level": "moderate", "confidence": 0.40}
    state = make_state(symptoms=["vague pain"], followup_count=1)

    from backend.src.nodes.risk_evaluation_node import risk_evaluation_node
    result = run(risk_evaluation_node(state))

    assert result["next_action"] == "ask_followup"


@patch(MOCK_EVAL)
def test_low_confidence_budget_exhausted_proceeds(mock_eval):
    """Low confidence but followup_count=3 → proceed without asking."""
    mock_eval.return_value = {"risk_score": 4.0, "risk_level": "moderate", "confidence": 0.40}
    state = make_state(followup_count=3)

    from backend.src.nodes.risk_evaluation_node import risk_evaluation_node
    result = run(risk_evaluation_node(state))

    assert result["next_action"] == ""


@patch(MOCK_EVAL)
def test_critical_high_confidence_triggers_interrupt(mock_eval):
    """Critical risk + confidence >= 0.85 → priority_interrupt."""
    mock_eval.return_value = {"risk_score": 9.5, "risk_level": "critical", "confidence": 0.92}
    state = make_state(symptoms=["chest pain", "arm numbness"])

    from backend.src.nodes.risk_evaluation_node import risk_evaluation_node
    result = run(risk_evaluation_node(state))

    assert result["next_action"] == "priority_interrupt"
    assert result["risk_level"] == "critical"


@patch(MOCK_EVAL)
def test_high_risk_not_critical_proceeds_normally(mock_eval):
    """High risk but NOT critical → proceeds to mental_health without interrupt."""
    mock_eval.return_value = {"risk_score": 7.5, "risk_level": "high", "confidence": 0.80}
    state = make_state()

    from backend.src.nodes.risk_evaluation_node import risk_evaluation_node
    result = run(risk_evaluation_node(state))

    assert result["next_action"] == ""
    assert result["risk_level"] == "high"


@patch(MOCK_EVAL)
def test_raw_user_input_is_used_when_symptoms_are_empty(mock_eval):
    """Critical phrases in raw user input still trigger interrupt if extraction missed them."""
    mock_eval.return_value = {"risk_score": 9.5, "risk_level": "critical", "confidence": 0.95}
    state = make_state(
        symptoms=[],
        user_input="I am suffering from heart attack",
        messages=[{"role": "user", "content": "I am suffering from heart attack"}],
    )

    from backend.src.nodes.risk_evaluation_node import risk_evaluation_node
    result = run(risk_evaluation_node(state))

    called_symptoms = mock_eval.call_args.kwargs["symptoms"]
    assert called_symptoms == ["I am suffering from heart attack"]
    assert result["risk_level"] == "critical"
    assert result["next_action"] == "priority_interrupt"
