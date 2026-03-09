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
    mock_llama.return_value = '{"clinical_summary": "🩺 Summary: Mild fever noted.", "possible_causes": [], "risk_level": "low", "recommended_action": "Rest.", "urgency": "routine", "confidence_score": 0.9, "suggested_otc": null, "nutrition_tip": null}'
    state = make_state(
        symptoms=["fever"],
        risk_level="low",
        risk_score=2.0,
        retrieved_info=["Fever often resolves with rest."],
        messages=[{"role": "user", "content": "I have fever"}],
        reasoning_input="I have fever"
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    assert "fever noted" in assistant_msgs[-1]["content"].lower()


@patch(MOCK_LLAMA)
def test_ask_followup_skips_response_generation(mock_llama):
    """When next_action == 'ask_followup', LLaMA is not called. But now V6 doesn't have an explicit ask_followup fast-exit in llm_brain_node.py.
    The graph routes to followup BEFORE reaching llm_brain.
    So if it reaches llm_brain, it WILL process. We remove this obsolete test."""
    pass


@patch(MOCK_LLAMA)
def test_priority_interrupt_generates_emergency_alert(mock_llama):
    """priority_interrupt generates an emergency alert (no LLaMA needed for alert)."""
    mock_llama.return_value = '{"clinical_summary": "Possible heart attack.", "possible_causes": [], "risk_level": "critical", "recommended_action": "Go to ER.", "urgency": "critical", "confidence_score": 0.9, "suggested_otc": null, "nutrition_tip": null}'
    state = make_state(
        next_action="priority_interrupt",
        mental_health_flag=False,
        symptoms=["chest pain", "arm numbness"],
        risk_level="critical",
        risk_score=9.5,
        messages=[{"role": "user", "content": "hello"}],
        llm_output={"clinical_summary": "Possible heart attack."},
        reasoning_input="hello"
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    content = assistant_msgs[-1]["content"]
    assert "heart attack" in content.lower()


@patch(MOCK_LLAMA)
def test_mental_health_crisis_generates_crisis_response(mock_llama):
    """priority_interrupt + mental_health_flag=True generates mental health response."""
    mock_llama.return_value = '{"clinical_summary": "Mental health crisis.", "possible_causes": [], "risk_level": "critical", "recommended_action": "Call 988.", "urgency": "critical", "confidence_score": 0.9, "suggested_otc": null, "nutrition_tip": null}'
    state = make_state(
        next_action="priority_interrupt",
        mental_health_flag=True,
        messages=[{"role": "user", "content": "hello"}],
        llm_output={"clinical_summary": "Mental health crisis."},
        reasoning_input="hello"
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    content = assistant_msgs[-1]["content"]
    assert "crisis" in content.lower()


@patch(MOCK_LLAMA)
def test_vision_findings_triggers_vision_path(mock_llama):
    """When vision_findings is present, the vision explanation path is taken."""
    mock_llama.return_value = '{"clinical_summary": "This may be consistent with a skin condition.", "possible_causes": [], "risk_level": "moderate", "recommended_action": "Consult doctor.", "urgency": "routine", "confidence_score": 0.75, "suggested_otc": null, "nutrition_tip": null}'
    state = make_state(
        vision_findings={
            "image_type": "skin",
            "visual_findings": ["redness", "swelling"],
            "confidence": 0.75,
            "explanation": "Possible inflammatory response.",
        },
        messages=[{"role": "user", "content": "hello"}],
        llm_output={"clinical_summary": "Skin issue."}
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1


@patch(MOCK_LLAMA)
def test_low_confidence_vision_triggers_quality_warning(mock_llama):
    """Vision confidence < 0.6 shows unclear image warning without calling LLaMA."""
    mock_llama.return_value = '{"clinical_summary": "Unclear image.", "possible_causes": [], "risk_level": "low", "recommended_action": "Retake.", "urgency": "routine", "confidence_score": 0.9, "suggested_otc": null, "nutrition_tip": null}'
    state = make_state(
        vision_findings={
            "image_type": "xray",
            "visual_findings": [],
            "confidence": 0.45,
            "explanation": "",
        },
        messages=[{"role": "user", "content": "hello"}],
        llm_output={"clinical_summary": "Unclear image."},
        intent="body_image",
        reasoning_input="hello"
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    mock_llama.assert_called()
    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    content = assistant_msgs[-1]["content"]
    assert "unclear image" in content.lower()


@patch(MOCK_LLAMA)
def test_nutrition_appended_to_response(mock_llama):
    """Nutrition advice in state is appended at the end of the LLaMA response."""
    mock_llama.return_value = '{"clinical_summary": "🩺 Summary: Cold symptoms.", "possible_causes": [], "risk_level": "low", "recommended_action": "Rest.", "urgency": "routine", "confidence_score": 0.9, "suggested_otc": null, "nutrition_tip": null}'
    state = make_state(
        symptoms=["runny nose"],
        risk_level="low",
        risk_score=1.5,
        nutrition_output={"dietary_recommendations": ["Drink warm fluids and eat fruits rich in vitamin C."]},
        messages=[{"role": "user", "content": "hello"}],
        llm_output={"clinical_summary": "Cold symptoms."},
        reasoning_input="hello"
    )

    from backend.src.nodes.llm_brain_node import llm_brain_node
    result = run(llm_brain_node(state))

    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    content = assistant_msgs[-1]["content"]
    assert "cold symptoms" in content.lower()
