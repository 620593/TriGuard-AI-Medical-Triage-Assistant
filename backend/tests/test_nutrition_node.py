"""
test_nutrition_node.py
-----------------------
Tests for nutrition_node: generates advice for low/moderate, skips for high/critical.
"""

import pytest
from unittest.mock import patch
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_NUTRITION = "backend.src.nodes.nutrition_node.generate_nutrition_advice"


@patch(MOCK_NUTRITION)
def test_nutrition_generated_for_low_risk(mock_nutrition):
    """Nutrition advice is generated for low-risk patients."""
    mock_nutrition.return_value = {"advice": "Eat fruits and vegetables.", "image_url": ""}
    state = make_state(symptoms=["mild cold"], risk_level="low")

    from backend.src.nodes.nutrition_node import nutrition_node
    result = run(nutrition_node(state))

    assert "Eat fruits" in result["nutrition_advice"]
    mock_nutrition.assert_called_once()


@patch(MOCK_NUTRITION)
def test_nutrition_generated_for_moderate_risk(mock_nutrition):
    """Nutrition advice is generated for moderate-risk patients."""
    mock_nutrition.return_value = {"advice": "Avoid spicy foods.", "image_url": "http://example.com/meal.jpg"}
    state = make_state(symptoms=["fever"], risk_level="moderate")

    from backend.src.nodes.nutrition_node import nutrition_node
    result = run(nutrition_node(state))

    assert result["nutrition_advice"] == "Avoid spicy foods."
    assert result["nutrition_image"] == "http://example.com/meal.jpg"


@patch(MOCK_NUTRITION)
def test_nutrition_skipped_for_high_risk(mock_nutrition):
    """High-risk patients get no nutrition advice (not appropriate for emergencies)."""
    state = make_state(risk_level="high")

    from backend.src.nodes.nutrition_node import nutrition_node
    result = run(nutrition_node(state))

    mock_nutrition.assert_not_called()
    assert result["nutrition_advice"] == ""
    assert result["nutrition_image"] == ""


@patch(MOCK_NUTRITION)
def test_nutrition_skipped_for_critical_risk(mock_nutrition):
    """Critical-risk patients get no nutrition advice."""
    state = make_state(risk_level="critical")

    from backend.src.nodes.nutrition_node import nutrition_node
    result = run(nutrition_node(state))

    mock_nutrition.assert_not_called()
    assert result["nutrition_advice"] == ""


@patch(MOCK_NUTRITION)
def test_nutrition_handles_tool_error_gracefully(mock_nutrition):
    """If nutrition tool throws, node doesn't crash and sets empty strings."""
    mock_nutrition.side_effect = Exception("HF API down")
    state = make_state(risk_level="low")

    from backend.src.nodes.nutrition_node import nutrition_node
    result = run(nutrition_node(state))  # Should not raise

    assert result["nutrition_advice"] == ""
    assert result["nutrition_image"] == ""
