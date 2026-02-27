"""
test_judge_validator_node.py
-----------------------------
Tests for judge_validator_node: PASS verdict, FAIL + regeneration, skip on followup/interrupt.
"""

import pytest
from unittest.mock import patch
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_LLAMA = "backend.src.nodes.judge_validator_node.call_llama"
MOCK_DB = "backend.src.nodes.judge_validator_node.insert_log"


@patch(MOCK_DB, return_value=None)
@patch(MOCK_LLAMA)
def test_judge_passes_valid_response(mock_llama, mock_db):
    """When LLaMA says PASS, judge_passed=True and response is unchanged."""
    mock_llama.return_value = "PASS"
    state = make_state(
        messages=[
            {"role": "user", "content": "I have fever"},
            {"role": "assistant", "content": "🩺 Summary: Mild fever. See a doctor."},
        ],
        retrieved_info=["Fever can indicate infection."],
        risk_level="low",
        risk_score=2.0,
    )

    from backend.src.nodes.judge_validator_node import judge_validator_node
    result = run(judge_validator_node(state))

    assert result["judge_passed"] is True
    assert result["judge_feedback"] == ""


@patch(MOCK_DB, return_value=None)
@patch(MOCK_LLAMA)
def test_judge_fails_and_regenerates(mock_llama, mock_db):
    """When LLaMA says FAIL, judge_passed=False and regeneration_count is incremented.

    V4 behavior: The judge does NOT regenerate inline. It sets judge_passed=False
    and increments regeneration_count. The graph conditional edge routes back to
    llm_brain for a retry.
    """
    mock_llama.return_value = "FAIL — mentions 'diabetes' not in context"
    state = make_state(
        messages=[
            {"role": "user", "content": "I have fever"},
            {"role": "assistant", "content": "You have diabetes (high risk)."},
        ],
        retrieved_info=["Fever can indicate infection."],
        risk_level="moderate",
        risk_score=5.0,
        regeneration_count=0,
    )

    from backend.src.nodes.judge_validator_node import judge_validator_node
    result = run(judge_validator_node(state))

    # V4: judge_passed stays False, regeneration_count incremented for graph retry
    assert result["judge_passed"] is False
    assert result["regeneration_count"] == 1
    assert "FAIL" in result["judge_feedback"]


@patch(MOCK_DB, return_value=None)
@patch(MOCK_LLAMA)
def test_judge_skipped_for_followup(mock_llama, mock_db):
    """Judge is skipped when next_action == 'ask_followup'."""
    state = make_state(next_action="ask_followup")

    from backend.src.nodes.judge_validator_node import judge_validator_node
    result = run(judge_validator_node(state))

    mock_llama.assert_not_called()
    assert result["judge_passed"] is True


@patch(MOCK_DB, return_value=None)
@patch(MOCK_LLAMA)
def test_judge_skipped_for_priority_interrupt(mock_llama, mock_db):
    """Judge is skipped for emergency priority_interrupt."""
    state = make_state(next_action="priority_interrupt")

    from backend.src.nodes.judge_validator_node import judge_validator_node
    result = run(judge_validator_node(state))

    mock_llama.assert_not_called()
    assert result["judge_passed"] is True


@patch(MOCK_DB, return_value=None)
@patch(MOCK_LLAMA)
def test_judge_skipped_when_no_assistant_message(mock_llama, mock_db):
    """Judge is skipped if no assistant messages exist."""
    state = make_state(messages=[{"role": "user", "content": "Hello"}])

    from backend.src.nodes.judge_validator_node import judge_validator_node
    result = run(judge_validator_node(state))

    mock_llama.assert_not_called()
    assert result["judge_passed"] is True


@patch(MOCK_DB, return_value=None)
@patch(MOCK_LLAMA)
def test_judge_force_accepts_after_max_retries(mock_llama, mock_db):
    """After MAX_REGENERATION_ATTEMPTS, judge force-accepts with force_accepted=True.

    V4 behavior: judge_passed stays False to preserve semantic integrity,
    but force_accepted=True signals the graph to proceed.
    """
    mock_llama.return_value = "FAIL — still hallucinating"
    state = make_state(
        messages=[
            {"role": "user", "content": "I have headache"},
            {"role": "assistant", "content": "You might have a brain tumor."},
        ],
        retrieved_info=["Headache can be caused by tension or dehydration."],
        risk_level="low",
        risk_score=2.0,
        regeneration_count=1,  # Already at 1, this attempt makes it 2 (== MAX)
    )

    from backend.src.nodes.judge_validator_node import judge_validator_node
    result = run(judge_validator_node(state))

    assert result["judge_passed"] is False
    assert result["force_accepted"] is True
    assert result["regeneration_count"] == 2
    assert result["validated_response"] != ""
    assert "Force-accepted" in result["judge_feedback"]
