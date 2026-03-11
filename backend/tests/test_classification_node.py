"""
test_classification_node.py
---------------------------
Regression tests for intent classification safety behavior.
"""

from backend.tests.helpers import make_state
from backend.src.nodes.classification_node import classification_node


def test_greeting_with_critical_medical_phrase_routes_to_medical_text():
    state = make_state(
        input_mode="text",
        messages=[{"role": "user", "content": "hi i think i am having a heart attack"}],
    )

    result = classification_node(state)

    assert result["intent"] == "medical_text"
