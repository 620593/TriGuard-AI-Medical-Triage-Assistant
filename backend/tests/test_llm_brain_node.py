"""
test_llm_brain_node.py
-----------------------
Tests for llm_brain_node: standard response, vision path, emergency path, nutrition append.
"""

import pytest
from unittest.mock import patch, AsyncMock
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_LLAMA = "backend.src.nodes.llm_brain_node.call_llama"


@patch(MOCK_LLAMA)
def test_standard_response_appended_to_messages(mock_llama):
    """Standard non-emergency, non-vision path generates and appends a response."""
    mock_llama.return_value = "🩺 Summary: Mild fever noted."
    state = make_state(
        symptoms=["fever"],
        risk_level="low",
        risk_score=2.0,
        retrieved_info=["Fever often resolves with rest."],
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    assert "DISCLAIMER" in assistant_msgs[-1]["content"]


@patch(MOCK_LLAMA)
def test_ask_followup_skips_response_generation(mock_llama):
    """When next_action == 'ask_followup', LLaMA is not called."""
    state = make_state(next_action="ask_followup")

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    mock_llama.assert_not_called()


@patch(MOCK_LLAMA)
def test_priority_interrupt_generates_emergency_alert(mock_llama):
    """priority_interrupt generates an emergency alert (no LLaMA needed for alert)."""
    state = make_state(
        next_action="priority_interrupt",
        mental_health_flag=False,
        symptoms=["chest pain", "arm numbness"],
        risk_level="critical",
        risk_score=9.5,
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert any("emergency" in m["content"].lower() or "urgent" in m["content"].lower()
               for m in assistant_msgs)


@patch(MOCK_LLAMA)
def test_mental_health_crisis_generates_crisis_response(mock_llama):
    """priority_interrupt + mental_health_flag=True generates mental health response."""
    state = make_state(
        next_action="priority_interrupt",
        mental_health_flag=True,
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    content = " ".join(m["content"] for m in assistant_msgs)
    assert "988" in content or "crisis" in content.lower() or "support" in content.lower()


@patch(MOCK_LLAMA)
def test_vision_findings_triggers_vision_path(mock_llama):
    """When vision_findings is present, the vision explanation path is taken."""
    mock_llama.return_value = "This may be consistent with a skin condition."
    state = make_state(
        vision_findings={
            "image_type": "skin",
            "visual_findings": ["redness", "swelling"],
            "confidence": 0.75,
            "explanation": "Possible inflammatory response.",
        }
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1


@patch(MOCK_LLAMA)
def test_low_confidence_vision_triggers_quality_warning(mock_llama):
    """Vision confidence < 0.6 shows unclear image warning without calling LLaMA."""
    state = make_state(
        vision_findings={
            "image_type": "xray",
            "visual_findings": [],
            "confidence": 0.45,
            "explanation": "",
        }
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    mock_llama.assert_not_called()
    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    content = assistant_msgs[-1]["content"]
    assert "quality" in content.lower() or "clearer" in content.lower() or "insufficient" in content.lower()


@patch(MOCK_LLAMA)
def test_nutrition_appended_to_response(mock_llama):
    """Nutrition advice in state is appended at the end of the LLaMA response."""
    mock_llama.return_value = "🩺 Summary: Cold symptoms."
    state = make_state(
        symptoms=["runny nose"],
        risk_level="low",
        risk_score=1.5,
        nutrition_advice="Drink warm fluids and eat fruits rich in vitamin C.",
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    content = assistant_msgs[-1]["content"]
    assert "vitamin C" in content or "Nutrition" in content
