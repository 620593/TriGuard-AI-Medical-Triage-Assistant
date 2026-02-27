"""
test_mental_health_node.py
---------------------------
Tests for mental_health_node: crisis detection, risk escalation, normal case.
"""

import pytest
from unittest.mock import patch
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_DETECT = "backend.src.nodes.mental_health_node.detect_mental_health_crisis"


@patch(MOCK_DETECT)
def test_crisis_detected_sets_flag_and_escalates(mock_detect):
    """When crisis is detected, mental_health_flag=True and risk is escalated."""
    mock_detect.return_value = True
    state = make_state(
        messages=[{"role": "user", "content": "I don't want to live anymore"}],
        risk_level="low",
        risk_score=1.0,
    )

    from backend.src.nodes.mental_health_node import mental_health_node
    result = run(mental_health_node(state))

    assert result["mental_health_flag"] is True
    assert result["risk_level"] in ("high", "critical")
    assert result["risk_score"] >= 7.5
    assert result["next_action"] == "priority_interrupt"


@patch(MOCK_DETECT)
def test_no_crisis_leaves_state_unchanged(mock_detect):
    """When no crisis is detected, state is unchanged."""
    mock_detect.return_value = False
    state = make_state(risk_level="low", risk_score=2.0)

    from backend.src.nodes.mental_health_node import mental_health_node
    result = run(mental_health_node(state))

    assert result["mental_health_flag"] is False
    assert result["risk_level"] == "low"
    assert result["next_action"] == ""


@patch(MOCK_DETECT)
def test_crisis_does_not_downgrade_existing_high_risk(mock_detect):
    """If risk is already 'critical', crisis detection should not downgrade it."""
    mock_detect.return_value = True
    state = make_state(risk_level="critical", risk_score=9.0)

    from backend.src.nodes.mental_health_node import mental_health_node
    result = run(mental_health_node(state))

    assert result["risk_level"] == "critical"
    assert result["risk_score"] == 9.0  # Unchanged
    assert result["mental_health_flag"] is True
