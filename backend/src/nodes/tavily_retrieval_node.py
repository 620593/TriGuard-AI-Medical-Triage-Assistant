"""
tavily_retrieval_node.py  (Version 3)
---------------------------------------
Calls Tavily API for grounded medical information.

V3 changes:
    - Structured logging with latency tracking.
    - Otherwise identical to V2 (already hardened).
"""

from backend.src.tools.tavily_tool import search_medical_info
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event, LatencyTracker

logger = get_logger("tavily_retrieval")


def tavily_retrieval_node(state: TriageState) -> TriageState:
    """
    Retrieves up to 3 medical summaries from Tavily using current symptoms.

    Args:
        state: Contains symptoms list.

    Returns:
        TriageState: With retrieved_info filled and next_action set.
    """
    symptoms = state.get("symptoms", [])

    with LatencyTracker("tavily_search") as tracker:
        results = search_medical_info(symptoms)

    state["retrieved_info"] = results

    log_event(logger, "tavily_retrieval",
              symptom_count=len(symptoms),
              results_count=len(results),
              latency_ms=tracker.duration_ms)

    # Anti-hallucination gate: no results + budget left → ask for clarification
    if not results and state.get("followup_count", 0) < 3:
        state["next_action"] = "ask_followup"
    else:
        state["next_action"] = ""

    return state
