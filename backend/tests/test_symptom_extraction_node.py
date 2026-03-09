"""
test_symptom_extraction_node.py
---------------------------------
Tests for symptom_extraction_node: extraction, merging, multilingual handling.
"""

import pytest
from unittest.mock import patch, AsyncMock
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_LLAMA = "backend.src.nodes.symptom_extraction_node.call_llama"


@patch(MOCK_LLAMA)
def test_symptoms_extracted_from_english(mock_llama):
    """Basic extraction: LLaMA returns a comma-separated symptom list."""
    # The input is English, so language detection is skipped, translation is skipped.
    # Only the extraction call is made.
    mock_llama.return_value = "fever, cough, headache"
    state = make_state(messages=[{"role": "user", "content": "I have fever, cough and headache"}])

    from backend.src.nodes.symptom_extraction_node import symptom_extraction_node
    result = run(symptom_extraction_node(state))

    assert "fever" in result["symptoms"]
    assert "cough" in result["symptoms"]
    assert "headache" in result["symptoms"]


@patch(MOCK_LLAMA)
def test_no_symptoms_returns_state_unchanged(mock_llama):
    """If LLaMA returns 'none', symptoms list stays empty."""
    mock_llama.side_effect = ["en", "none"]
    state = make_state(messages=[{"role": "user", "content": "I feel fine today."}])

    from backend.src.nodes.symptom_extraction_node import symptom_extraction_node
    result = run(symptom_extraction_node(state))

    assert result["symptoms"] == []


@patch(MOCK_LLAMA)
def test_symptoms_merged_with_existing(mock_llama):
    """Existing symptoms are merged with newly extracted ones (union, no duplicates)."""
    # Only the extraction call is made since input is English
    mock_llama.return_value = "nausea, vomiting"
    state = make_state(
        symptoms=["fever"],
        messages=[{"role": "user", "content": "Also feeling nauseous and vomiting"}]
    )

    from backend.src.nodes.symptom_extraction_node import symptom_extraction_node
    result = run(symptom_extraction_node(state))

    assert "fever" in result["symptoms"]
    assert "nausea" in result["symptoms"]
    assert "vomiting" in result["symptoms"]


@patch(MOCK_LLAMA)
def test_empty_messages_returns_state(mock_llama):
    """If there are no user messages, state is returned unchanged."""
    state = make_state(messages=[])

    from backend.src.nodes.symptom_extraction_node import symptom_extraction_node
    result = run(symptom_extraction_node(state))

    mock_llama.assert_not_called()
    assert result["symptoms"] == []


@patch(MOCK_LLAMA)
def test_non_english_input_translated_first(mock_llama):
    """Non-English input is detected and translated before extraction."""
    # lang detection returns 'hi', then translation, then extraction
    mock_llama.side_effect = ["hi", "I have fever and cough", "fever, cough"]
    state = make_state(
        language="en",
        messages=[{"role": "user", "content": "मुझे बुखार और खांसी है"}]
    )

    from backend.src.nodes.symptom_extraction_node import symptom_extraction_node
    result = run(symptom_extraction_node(state))

    assert result["language"] == "hi"
    assert "fever" in result["symptoms"] or "cough" in result["symptoms"]


@patch(MOCK_LLAMA)
def test_duplicate_symptoms_deduplicated(mock_llama):
    """If LLaMA returns a symptom already in the list, it isn't duplicated."""
    mock_llama.side_effect = ["en", "fever, cough"]
    state = make_state(
        symptoms=["fever"],
        messages=[{"role": "user", "content": "fever and cough"}]
    )

    from backend.src.nodes.symptom_extraction_node import symptom_extraction_node
    result = run(symptom_extraction_node(state))

    assert result["symptoms"].count("fever") == 1
