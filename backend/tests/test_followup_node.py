"""
test_followup_node.py
----------------------
Tests for followup_node: asks clarifying questions when needed, skips when confident.
"""

import pytest
from unittest.mock import patch
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_LLAMA = "backend.src.nodes.followup_node.call_llama"


@patch(MOCK_LLAMA)
def test_asks_followup_when_symptoms_vague(mock_llama):
    """With 0 symptoms and followup_count=0, the node generates a clarifying question."""
    mock_llama.return_value = "Can you describe your symptoms more?"
    state = make_state(symptoms=[], followup_count=0, risk_confidence=0.0)

    from backend.src.nodes.followup_node import followup_node
    result = run(followup_node(state))

    assert result["next_action"] == "ask_followup"
    assert result["followup_count"] == 1
    last_msg = result["messages"][-1]
    assert last_msg["role"] == "assistant"
    assert "?" in last_msg["content"] or len(last_msg["content"]) > 5


@patch(MOCK_LLAMA)
def test_skips_followup_when_enough_symptoms(mock_llama):
    """With 2+ symptoms, no follow-up is asked (MIN_SYMPTOMS=2 threshold)."""
    state = make_state(symptoms=["fever", "cough"], followup_count=0)

    from backend.src.nodes.followup_node import followup_node
    result = run(followup_node(state))

    mock_llama.assert_not_called()
    assert result["next_action"] == ""


@patch(MOCK_LLAMA)
def test_skips_followup_when_budget_exhausted(mock_llama):
    """With followup_count >= 3, no more questions are asked."""
    state = make_state(symptoms=[], followup_count=3)

    from backend.src.nodes.followup_node import followup_node
    result = run(followup_node(state))

    mock_llama.assert_not_called()
    assert result["next_action"] == ""


@patch(MOCK_LLAMA)
def test_skips_followup_when_high_confidence(mock_llama):
    """With risk_confidence >= 0.75 (HIGH_CONFIDENCE), no follow-up is asked."""
    state = make_state(symptoms=["fever"], followup_count=0, risk_confidence=0.80)

    from backend.src.nodes.followup_node import followup_node
    result = run(followup_node(state))

    mock_llama.assert_not_called()
    assert result["next_action"] == ""


@patch(MOCK_LLAMA)
def test_fallback_question_if_llama_returns_empty(mock_llama):
    """If LLaMA returns empty, a default fallback question is used."""
    mock_llama.return_value = ""
    state = make_state(symptoms=[], followup_count=0, risk_confidence=0.0)

    from backend.src.nodes.followup_node import followup_node
    result = run(followup_node(state))

    assert result["next_action"] == "ask_followup"
    last_msg = result["messages"][-1]["content"]
    assert "symptom" in last_msg.lower() or "describe" in last_msg.lower()
