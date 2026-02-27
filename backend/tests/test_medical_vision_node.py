"""
test_medical_vision_node.py
----------------------------
Tests for medical_vision_node: image processing, size guard, error handling.
"""

import pytest
from unittest.mock import AsyncMock, patch
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_ANALYZE = "backend.src.nodes.medical_vision_node.analyze_medical_image"


@patch(MOCK_ANALYZE, new_callable=AsyncMock)
def test_image_analyzed_successfully(mock_analyze):
    """Valid image bytes are passed to analyze_medical_image and findings stored."""
    mock_analyze.return_value = {
        "image_type": "skin",
        "visual_findings": ["redness", "scaling"],
        "confidence": 0.82,
        "explanation": "May indicate psoriasis.",
    }
    state = make_state(
        input_mode="image",
        image_input=b"\xff\xd8\xff" + b"\x00" * 50,
    )

    from backend.src.nodes.medical_vision_node import medical_vision_node
    result = run(medical_vision_node(state))

    assert result["vision_findings"]["image_type"] == "skin"
    assert result["vision_findings"]["confidence"] == 0.82
    assert result["image_input"] is None  # MUST be cleared after processing


@patch(MOCK_ANALYZE, new_callable=AsyncMock)
def test_no_image_data_skips_analysis(mock_analyze):
    """When image_input is None, analysis is skipped."""
    state = make_state(input_mode="image", image_input=None)

    from backend.src.nodes.medical_vision_node import medical_vision_node
    result = run(medical_vision_node(state))

    mock_analyze.assert_not_called()


@patch(MOCK_ANALYZE, new_callable=AsyncMock)
def test_oversized_image_rejected(mock_analyze):
    """Images >10MB are rejected with an error message in vision_findings."""
    big_image = b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)
    state = make_state(input_mode="image", image_input=big_image)

    from backend.src.nodes.medical_vision_node import medical_vision_node
    result = run(medical_vision_node(state))

    mock_analyze.assert_not_called()
    assert result["image_input"] is None
    assert "too large" in result["vision_findings"]["explanation"].lower()


@patch(MOCK_ANALYZE, new_callable=AsyncMock)
def test_vision_error_handled_gracefully(mock_analyze):
    """If analyze_medical_image throws, node returns safe fallback findings."""
    mock_analyze.side_effect = Exception("Model unavailable")
    state = make_state(image_input=b"\xff\xd8\xff" + b"\x00" * 50)

    from backend.src.nodes.medical_vision_node import medical_vision_node
    result = run(medical_vision_node(state))  # Must not raise

    assert result["vision_findings"]["image_type"] == "unknown"
    assert result["vision_findings"]["confidence"] == 0.0
