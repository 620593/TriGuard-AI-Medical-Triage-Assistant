import pytest
from backend.src.nodes.disease_retrieval_node import disease_retrieval_node
from backend.tests.helpers import make_state


@pytest.mark.asyncio
async def test_disease_retrieval_node_empty_symptoms():
    """Test that when symptoms list is empty, disease_candidates is empty."""
    state = make_state(symptoms=[])
    result = await disease_retrieval_node(state)
    assert result["disease_candidates"] == []


@pytest.mark.asyncio
async def test_disease_retrieval_node_match():
    """Test that a matching symptom returns the correct diseases."""
    state = make_state(symptoms=["burn"])
    result = await disease_retrieval_node(state)
    assert result["disease_candidates"] == ["Burn injury", "Chemical burn", "Sunburn"]


@pytest.mark.asyncio
async def test_disease_retrieval_node_case_insensitive():
    """Test that uppercase or mixed case symptoms still match lowercase dictionary keys."""
    state = make_state(symptoms=["BURN"])
    result = await disease_retrieval_node(state)
    assert result["disease_candidates"] == ["Burn injury", "Chemical burn", "Sunburn"]


@pytest.mark.asyncio
async def test_disease_retrieval_node_partial_match():
    """Test that a keyword found within a longer symptom string matches."""
    state = make_state(symptoms=["I have a bad burn"])
    result = await disease_retrieval_node(state)
    assert result["disease_candidates"] == ["Burn injury", "Chemical burn", "Sunburn"]


@pytest.mark.asyncio
async def test_disease_retrieval_node_no_match():
    """Test that an unrecognized symptom returns an empty list."""
    state = make_state(symptoms=["unknown_symptom"])
    result = await disease_retrieval_node(state)
    assert result["disease_candidates"] == []


@pytest.mark.asyncio
async def test_disease_retrieval_node_max_six_candidates():
    """Test that the number of disease candidates is capped at 6."""
    # "burn" provides 3: ["Burn injury", "Chemical burn", "Sunburn"]
    # "insomnia" provides 4: ["Sleep disorder", "Anxiety", "Depression", "Sleep apnea"]
    # Total combined without cap = 7. Cap should limit to 6.
    state = make_state(symptoms=["burn", "insomnia"])
    result = await disease_retrieval_node(state)
    assert len(result["disease_candidates"]) == 6
    assert result["disease_candidates"] == [
        "Burn injury",
        "Chemical burn",
        "Sunburn",
        "Sleep disorder",
        "Anxiety",
        "Depression",
    ]


@pytest.mark.asyncio
async def test_disease_retrieval_node_no_duplicates():
    """Test that overlapping diseases from different symptoms are not duplicated."""
    # "shortness" maps to ["Asthma", "COPD", "Pneumonia", "Heart failure", "Pulmonary embolism"]
    # "breath" maps to the exact same list.
    # Total combined uniquely should be 5.
    state = make_state(symptoms=["shortness", "breath"])
    result = await disease_retrieval_node(state)
    assert len(result["disease_candidates"]) == 5
    assert result["disease_candidates"] == [
        "Asthma",
        "COPD",
        "Pneumonia",
        "Heart failure",
        "Pulmonary embolism",
    ]
