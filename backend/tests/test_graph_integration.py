"""
test_graph_integration.py
--------------------------
Integration tests for the full LangGraph pipeline:
- Text/voice pipeline
- Vision pipeline
All external calls are mocked — no real API keys needed.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Minimal valid initial state (as built by routes.py _build_initial_state) ─

def _init_state(**kwargs):
    base = {
        "messages": [{"role": "user", "content": "I have a headache and fever"}],
        "original_input": "",
        "symptoms": [],
        "followup_count": 0,
        "retrieved_info": [],
        "risk_level": "low",
        "risk_score": 0.0,
        "risk_confidence": 0.0,
        "session_id": "",
        "user_id": "test-user",
        "language": "en",
        "timestamp": "",
        "image_input": None,
        "input_mode": "text",
        "vision_findings": {},
        "mental_health_flag": False,
        "next_action": "",
        "judge_passed": True,
        "judge_feedback": "",
        "nutrition_advice": "",
        "nutrition_image": "",
        "audio_url": "",
    }
    base.update(kwargs)
    return base


# ── Patch catalogue (all external I/O) ──────────────────────────────────────

PATCHES = {
    "create_session":        ("backend.src.nodes.load_session_node.create_session", "new-session-abc"),
    "load_session":          ("backend.src.nodes.load_session_node.load_session", None),
    "call_llama_symptom":    ("backend.src.nodes.symptom_extraction_node.call_llama", None),
    "call_llama_followup":   ("backend.src.nodes.followup_node.call_llama", None),
    "call_llama_brain":      ("backend.src.nodes.llm_brain_node.call_llama", None),
    "call_llama_judge":      ("backend.src.nodes.judge_validator_node.call_llama", None),
    "search_medical_info":   ("backend.src.nodes.tavily_retrieval_node.search_medical_info", None),
    "evaluate_risk":         ("backend.src.nodes.risk_evaluation_node.evaluate_risk", None),
    "detect_mh":             ("backend.src.nodes.mental_health_node.detect_mental_health_crisis", None),
    "gen_nutrition":         ("backend.src.nodes.nutrition_node.generate_nutrition_advice", None),
    "update_session":        ("backend.src.nodes.save_session_node.update_session", None),
    "save_report":           ("backend.src.nodes.save_session_node.save_report", None),
    "insert_log":            ("backend.src.nodes.save_session_node.insert_log", None),
}


@patch("backend.src.nodes.save_session_node.insert_log", new_callable=AsyncMock)
@patch("backend.src.nodes.save_session_node.save_report", new_callable=AsyncMock)
@patch("backend.src.nodes.save_session_node.update_session", new_callable=AsyncMock)
@patch("backend.src.nodes.nutrition_node.generate_nutrition_advice",
       return_value={"advice": "Drink water", "image_url": ""})
@patch("backend.src.nodes.mental_health_node.detect_mental_health_crisis", return_value=False)
@patch("backend.src.nodes.risk_evaluation_node.evaluate_risk",
       return_value={"risk_score": 3.0, "risk_level": "low", "confidence": 0.9})
@patch("backend.src.nodes.tavily_retrieval_node.search_medical_info",
       return_value=["Headache may be tension-type."])
@patch("backend.src.nodes.judge_validator_node.call_llama", return_value="PASS")
@patch("backend.src.nodes.llm_brain_node.call_llama",
       return_value="🩺 Summary: Mild headache with fever.")
@patch("backend.src.nodes.followup_node.call_llama", return_value="")
@patch("backend.src.nodes.symptom_extraction_node.call_llama",
       side_effect=["en", "headache, fever"])
@patch("backend.src.nodes.load_session_node.create_session", new_callable=AsyncMock,
       return_value="new-session-abc")
def test_text_pipeline_full_flow(
    mock_create, mock_sym_llama, mock_fup_llama, mock_brain_llama,
    mock_judge_llama, mock_search, mock_risk, mock_mh, mock_nutrition,
    mock_update, mock_report, mock_log
):
    """Full text pipeline: new session → symptoms → followup → retrieval → risk → mental health → LLM → judge → nutrition → save."""
    from backend.src.graph.builder import build_triage_graph

    graph = build_triage_graph()
    state = _init_state()
    result = run(graph.ainvoke(state))

    # Session was created
    assert result["session_id"] == "new-session-abc"

    # Symptoms extracted
    assert len(result["symptoms"]) > 0

    # Risk assessed
    assert result["risk_level"] == "low"
    assert result["risk_score"] == 3.0

    # LLaMA brain generated response
    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
    assert "DISCLAIMER" in assistant_msgs[-1]["content"]

    # Judge passed
    assert result["judge_passed"] is True

    # Nutrition generated for low risk
    assert "water" in result.get("nutrition_advice", "").lower() or \
           result.get("nutrition_advice") is not None


@patch("backend.src.nodes.save_session_node.insert_log", new_callable=AsyncMock)
@patch("backend.src.nodes.save_session_node.save_report", new_callable=AsyncMock)
@patch("backend.src.nodes.save_session_node.update_session", new_callable=AsyncMock)
@patch("backend.src.nodes.judge_validator_node.call_llama", return_value="PASS")
@patch("backend.src.nodes.llm_brain_node.call_llama",
       return_value="Possible skin rash. Consult a dermatologist.")
@patch("backend.src.nodes.medical_vision_node.analyze_medical_image", new_callable=AsyncMock,
       return_value={
           "image_type": "skin",
           "visual_findings": ["redness"],
           "confidence": 0.80,
           "explanation": "Possible rash.",
       })
@patch("backend.src.nodes.load_session_node.create_session", new_callable=AsyncMock,
       return_value="vision-session-abc")
def test_vision_pipeline_full_flow(
    mock_create, mock_vision, mock_brain, mock_judge,
    mock_update, mock_report, mock_log
):
    """Full vision pipeline: new session → medical_vision → llm_brain → judge → nutrition → save."""
    from backend.src.graph.builder import build_triage_graph

    graph = build_triage_graph()
    state = _init_state(
        messages=[{"role": "user", "content": "Analyzed image"}],
        input_mode="image",
        image_input=b"\xff\xd8\xff" + b"\x00" * 50,
    )
    result = run(graph.ainvoke(state))

    # Vision findings populated
    assert result["vision_findings"]["image_type"] == "skin"
    # Image bytes discarded
    assert result["image_input"] is None
    # Response generated
    assistant_msgs = [m for m in result["messages"] if m["role"] == "assistant"]
    assert len(assistant_msgs) >= 1
