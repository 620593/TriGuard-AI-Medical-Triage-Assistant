"""
test_xray_analysis_node.py
----------------------------
Tests for xray_analysis_node: fallback handling, normal processing, and skipped execution.
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.tests.helpers import make_state
from backend.src.nodes.xray_analysis_node import xray_analysis_node, _XRAY_FALLBACK_MSG

MOCK_ANALYZE_XRAY = "backend.src.nodes.xray_analysis_node.analyze_xray"
MOCK_CALL_LLAMA = "backend.src.nodes.xray_analysis_node.call_llama"

def test_xray_node_skipped_when_wrong_mode():
    """Node should skip execution if input_mode is not 'xray'."""
    state = make_state(input_mode="text", image_input=b"fake_image")
    # Delete default empty dict to test if it gets populated
    state.pop("xray_findings", None)
    result = xray_analysis_node(state)
    assert "xray_findings" not in result

def test_xray_node_skipped_when_no_image():
    """Node should skip execution if image_input is missing."""
    state = make_state(input_mode="xray", image_input=None)
    state.pop("xray_findings", None)
    result = xray_analysis_node(state)
    assert "xray_findings" not in result

@patch(MOCK_ANALYZE_XRAY)
def test_xray_model_failure_fallback(mock_analyze):
    """
    Test the V4 Fix: when model returns confidence=0.0 and no labels,
    a safe fallback should be used without calling LLaMA.
    """
    mock_analyze.return_value = {
        "findings": "Unable to analyze X-ray image.",
        "confidence": 0.0,
        "raw_labels": [],
    }

    state = make_state(input_mode="xray", image_input=b"fake_image_bytes", messages=[])

    # Run the node
    result = xray_analysis_node(state)

    assert result["xray_findings"] == _XRAY_FALLBACK_MSG
    assert result["image_input"] is None

    # Verify the message was appended correctly
    assert len(result["messages"]) == 1
    assert result["messages"][0]["role"] == "assistant"
    assert result["messages"][0]["content"] == _XRAY_FALLBACK_MSG

@patch(MOCK_ANALYZE_XRAY)
@patch(MOCK_CALL_LLAMA)
def test_xray_analyzed_successfully(mock_call_llama, mock_analyze):
    """
    Test successful X-ray analysis where LLaMA translates findings.
    """
    mock_analyze.return_value = {
        "findings": "Potential findings: pneumonia (90%).",
        "confidence": 0.90,
        "raw_labels": [{"label": "pneumonia", "score": 0.90}],
    }

    mock_call_llama.return_value = "The AI model suggests there may be signs of pneumonia."

    state = make_state(
        input_mode="xray",
        image_input=b"fake_image_bytes",
        messages=[],
        risk_score=0.0,
        risk_level="low"
    )

    result = xray_analysis_node(state)

    # Expected suffix
    suffix = "\n\n⚠️ IMPORTANT: This is an AI screening tool, NOT a radiological diagnosis. These findings MUST be reviewed by a qualified radiologist before any clinical decisions."

    expected_findings = "The AI model suggests there may be signs of pneumonia." + suffix

    assert result["xray_findings"] == expected_findings
    assert result["image_input"] is None

    # Should elevate risk
    assert result["risk_score"] == 5.0
    assert result["risk_level"] == "moderate"

    assert len(result["messages"]) == 1
    assert result["messages"][0]["content"] == f"🫁 X-Ray Analysis:\n\n{expected_findings}"

@patch(MOCK_ANALYZE_XRAY)
@patch(MOCK_CALL_LLAMA)
def test_xray_analyzed_normal(mock_call_llama, mock_analyze):
    """
    Test successful X-ray analysis of a normal chest X-ray.
    Risk should not be elevated.
    """
    mock_analyze.return_value = {
        "findings": "No significant abnormalities detected in the X-ray.",
        "confidence": 0.95,
        "raw_labels": [{"label": "normal chest x-ray", "score": 0.95}],
    }

    mock_call_llama.return_value = "The AI model suggests the X-ray is normal."

    state = make_state(
        input_mode="xray",
        image_input=b"fake_image_bytes",
        messages=[],
        risk_score=2.0,
        risk_level="low"
    )

    result = xray_analysis_node(state)

    # Risk should remain unchanged since label is "normal chest x-ray"
    assert result["risk_score"] == 2.0
    assert result["risk_level"] == "low"
