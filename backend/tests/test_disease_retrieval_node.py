import pytest
from backend.src.nodes.disease_retrieval_node import disease_retrieval_node

@pytest.mark.asyncio
async def test_disease_retrieval_node():
    state = {"symptoms": ["I have a fever and cough"]}
    new_state = await disease_retrieval_node(state)
    assert "Viral infection" in new_state["disease_candidates"]
