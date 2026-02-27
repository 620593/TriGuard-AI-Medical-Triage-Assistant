"""
conftest.py
-----------
Shared pytest fixtures for TriGuard AI backend unit tests.
"""

import pytest
from backend.tests.helpers import make_state


@pytest.fixture
def base_state():
    """A minimal valid text-mode triage state."""
    return make_state()


@pytest.fixture
def symptom_state():
    """State with 2 confirmed symptoms (passes the MIN_SYMPTOMS threshold)."""
    return make_state(
        symptoms=["fever", "cough"],
        followup_count=0,
    )


@pytest.fixture
def high_risk_state():
    """State representing a high-risk patient."""
    return make_state(
        symptoms=["chest pain", "shortness of breath"],
        risk_level="high",
        risk_score=8.5,
        risk_confidence=0.9,
        retrieved_info=["Chest pain with dyspnoea may indicate cardiac event."],
    )


@pytest.fixture
def vision_state():
    """State for vision/image analysis."""
    return make_state(
        input_mode="image",
        image_input=b"\xff\xd8\xff" + b"\x00" * 100,
        vision_findings={},
    )
