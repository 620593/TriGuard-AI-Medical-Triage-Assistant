"""
test_tavily_retrieval_node.py
------------------------------
Tests for tavily_retrieval_node: successful retrieval, empty results, anti-hallucination gate.
"""

import pytest
from unittest.mock import patch
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_SEARCH = "backend.src.nodes.tavily_retrieval_node.search_medical_info"


@patch(MOCK_SEARCH)
def test_retrieval_populates_retrieved_info(mock_search):
    """Successful Tavily call fills retrieved_info with results."""
    mock_search.return_value = ["Fever may indicate infection.", "Stay hydrated."]
    state = make_state(symptoms=["fever", "cough"])

    from backend.src.nodes.tavily_retrieval_node import tavily_retrieval_node
    result = run(tavily_retrieval_node(state))

    assert len(result["retrieved_info"]) == 2
    assert result["next_action"] == ""


@patch(MOCK_SEARCH)
def test_empty_results_triggers_followup_gate(mock_search):
    """If Tavily returns nothing and followup_count < 3, ask_followup is set."""
    mock_search.return_value = []
    state = make_state(symptoms=["fever"], followup_count=0)

    from backend.src.nodes.tavily_retrieval_node import tavily_retrieval_node
    result = run(tavily_retrieval_node(state))

    assert result["retrieved_info"] == []
    assert result["next_action"] == "ask_followup"


@patch(MOCK_SEARCH)
def test_empty_results_budget_exhausted_proceeds(mock_search):
    """If Tavily returns nothing but followup_count=3, proceed (no more questions)."""
    mock_search.return_value = []
    state = make_state(symptoms=["fever"], followup_count=3)

    from backend.src.nodes.tavily_retrieval_node import tavily_retrieval_node
    result = run(tavily_retrieval_node(state))

    assert result["next_action"] == ""


@patch(MOCK_SEARCH)
def test_retrieval_passes_symptoms_to_tool(mock_search):
    """Tavily is called with the current symptom list from state."""
    mock_search.return_value = ["Some info"]
    symptoms = ["chest pain", "shortness of breath"]
    state = make_state(symptoms=symptoms)

    from backend.src.nodes.tavily_retrieval_node import tavily_retrieval_node
    run(tavily_retrieval_node(state))

    mock_search.assert_called_once_with(symptoms)
