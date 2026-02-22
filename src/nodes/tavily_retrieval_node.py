"""
tavily_retrieval_node.py  (Version 2)
--------------------------------------
Calls the Tavily API to fetch grounded medical information.

Changes from V1:
  - Renamed from disease_retrieval_node → tavily_retrieval_node (clearer).
  - Calls updated search_medical_info function (not the @tool wrapper).
  - If retrieval returns nothing AND follow-up budget remains → loop to followup_node.

Anti-hallucination:
  - retrieved_info is the ONLY allowed source for the final response.
  - If empty → next_action = 'ask_followup' (request more detail from user).

Input:
    state (TriageState): Contains symptoms and followup_count.

Returns:
    TriageState: State with retrieved_info populated (or []) and next_action set.
"""

from src.tools.tavily_tool import search_medical_info
from src.state.state import TriageState


def tavily_retrieval_node(state: TriageState) -> TriageState:
    """
    Retrieves up to 3 medical summaries from Tavily using current symptoms.

    Args:
        state (TriageState): Contains symptoms list.

    Returns:
        TriageState: With retrieved_info filled and next_action set appropriately.
    """
    symptoms = state.get("symptoms", [])

    # Fetch grounded medical context
    results = search_medical_info(symptoms)
    state["retrieved_info"] = results

    # Anti-hallucination gate: no results + budget left → ask for clarification
    if not results and state.get("followup_count", 0) < 3:
        state["next_action"] = "ask_followup"
    else:
        state["next_action"] = ""   # Proceed to risk evaluation

    return state
