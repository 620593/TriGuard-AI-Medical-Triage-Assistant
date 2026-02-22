"""
disease_retrieval_node.py
-------------------------
Calls the Tavily API tool to retrieve grounded medical information.
Populates state["retrieved_info"] with up to 3 real medical summaries.

Anti-hallucination contract:
  - If Tavily returns nothing, state["retrieved_info"] is set to [] and
    next_action is flipped to "ask_followup" so the graph requests more info.
"""

from backend.src.tools.tavily_tool import search_medical_info
from backend.src.state.state import TriageState


def disease_retrieval_node(state: TriageState) -> TriageState:
    """
    Retrieves grounded medical information from Tavily based on current symptoms.

    Why it exists:
        Disease context MUST come from a real external source to avoid hallucination.
        Tavily provides up-to-date, cited medical summaries we can reference safely.

    Args:
        state (TriageState): State containing collected symptoms.

    Returns:
        TriageState: State with retrieved_info populated (or empty).
    """
    symptoms = state.get("symptoms", [])

    # Invoke the Tavily tool with the current symptom list
    results = search_medical_info.invoke({"symptoms": symptoms})

    state["retrieved_info"] = results

    # Anti-hallucination gate: if we got nothing back, request more clarification
    if not results and state.get("followup_count", 0) < 3:
        state["next_action"] = "ask_followup"
    else:
        state["next_action"] = ""  # Proceed to risk evaluation

    return state
