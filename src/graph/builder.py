"""
builder.py  (Version 2)
------------------------
Constructs and compiles the V2 LangGraph StateGraph with conditional routing.

V2 Graph Flow:
  START
    → load_history_node
    → symptom_extraction_node
    → followup_node  ──(ask_followup)──┐
         ↓ (proceed)                   │ (loop back if more info needed)
    tavily_retrieval_node ─────────────┘
    → risk_evaluation_node
    → mental_health_node
    → llm_brain_node
    → save_history_node
    → END

Conditional routing:
  - After followup_node: if next_action == 'ask_followup' AND followup_count < 3
      → loop back to followup_node for more clarification.
  - After tavily_retrieval_node: if next_action == 'ask_followup'
      → route back to followup_node.
  - All other paths proceed linearly to llm_brain_node.
"""

from langgraph.graph import StateGraph, END, START

from src.state.state import TriageState
from src.nodes.load_history_node import load_history_node
from src.nodes.symptom_extraction_node import symptom_extraction_node
from src.nodes.followup_node import followup_node
from src.nodes.tavily_retrieval_node import tavily_retrieval_node
from src.nodes.risk_evaluation_node import risk_evaluation_node
from src.nodes.mental_health_node import mental_health_node
from src.nodes.llm_brain_node import llm_brain_node
from src.nodes.save_history_node import save_history_node


# ── Conditional router functions ───────────────────────────────────────────────

def route_after_followup(state: TriageState) -> str:
    """
    After followup_node: if still waiting for user → end turn early (save + exit).
    Otherwise → proceed to Tavily retrieval.
    """
    if state.get("next_action") == "ask_followup":
        # Save state and exit — wait for user's next turn
        return "save_history"
    return "tavily_retrieval"


def route_after_tavily(state: TriageState) -> str:
    """
    After Tavily retrieval: if no results and budget remains → ask followup.
    Otherwise → run risk evaluation.
    """
    if state.get("next_action") == "ask_followup":
        return "followup"        # Loop back to ask for better symptom input
    return "risk_evaluation"


def route_after_risk(state: TriageState) -> str:
    """
    After risk evaluation: if confidence too low → ask followup.
    Otherwise → mental health check.
    """
    if state.get("next_action") == "ask_followup":
        return "followup"        # One more clarification attempt
    return "mental_health"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_triage_graph() -> StateGraph:
    """
    Assembles and compiles the V2 medical triage LangGraph pipeline.

    Returns:
        Compiled LangGraph app (callable with .invoke(initial_state)).
    """
    graph = StateGraph(TriageState)

    # ── Register all nodes ─────────────────────────────────────────────────────
    graph.add_node("load_history",         load_history_node)
    graph.add_node("symptom_extraction",   symptom_extraction_node)
    graph.add_node("followup",             followup_node)
    graph.add_node("tavily_retrieval",     tavily_retrieval_node)
    graph.add_node("risk_evaluation",      risk_evaluation_node)
    graph.add_node("mental_health",        mental_health_node)
    graph.add_node("llm_brain",            llm_brain_node)
    graph.add_node("save_history",         save_history_node)

    # ── Linear edges (no branching needed here) ────────────────────────────────
    graph.add_edge(START,                "load_history")
    graph.add_edge("load_history",       "symptom_extraction")
    graph.add_edge("symptom_extraction", "followup")

    # ── Conditional edges ──────────────────────────────────────────────────────

    # After followup: either wait for user (save + end) or continue to Tavily
    graph.add_conditional_edges(
        "followup",
        route_after_followup,
        {"save_history": "save_history", "tavily_retrieval": "tavily_retrieval"},
    )

    # After Tavily: either loop to followup (no results) or risk evaluation
    graph.add_conditional_edges(
        "tavily_retrieval",
        route_after_tavily,
        {"followup": "followup", "risk_evaluation": "risk_evaluation"},
    )

    # After risk: either loop to followup (low confidence) or mental health check
    graph.add_conditional_edges(
        "risk_evaluation",
        route_after_risk,
        {"followup": "followup", "mental_health": "mental_health"},
    )

    # Linear tail: mental health → brain → save → END
    graph.add_edge("mental_health", "llm_brain")
    graph.add_edge("llm_brain",     "save_history")
    graph.add_edge("save_history",  END)

    return graph.compile()
