"""
builder.py  (Version 3)
-------------------------
LangGraph workflow definition for the V3 medical triage pipeline.

Graph topology:
    load_session → symptom_extraction → followup (conditional)
                                       ↓
                              tavily_retrieval → risk_evaluation → mental_health
                                                                       ↓
                                                              llm_brain → judge_validator
                                                                              ↓
                                                                      nutrition → save_session

Special mode branches:
    - OCR images: load_session → ocr_processing → save_session
    - X-ray:      load_session → xray_analysis → save_session
"""

from langgraph.graph import StateGraph, END

from backend.src.state.state import TriageState
from backend.src.nodes.load_session_node import load_session_node
from backend.src.nodes.symptom_extraction_node import symptom_extraction_node
from backend.src.nodes.followup_node import followup_node
from backend.src.nodes.tavily_retrieval_node import tavily_retrieval_node
from backend.src.nodes.risk_evaluation_node import risk_evaluation_node
from backend.src.nodes.mental_health_node import mental_health_node
from backend.src.nodes.llm_brain_node import llm_brain_node
from backend.src.nodes.judge_validator_node import judge_validator_node
from backend.src.nodes.nutrition_node import nutrition_node
from backend.src.nodes.ocr_processing_node import ocr_processing_node
from backend.src.nodes.xray_analysis_node import xray_analysis_node
from backend.src.nodes.save_session_node import save_session_node


def _route_input_mode(state: TriageState) -> str:
    """Routes to the appropriate pipeline based on input mode."""
    mode = state.get("input_mode", "text")
    if mode == "image":
        return "ocr_processing"
    elif mode == "xray":
        return "xray_analysis"
    else:
        return "symptom_extraction"


def _route_after_followup(state: TriageState) -> str:
    """Routes after follow-up: either wait for user input or proceed to retrieval."""
    if state.get("next_action") == "ask_followup":
        return "save_session"
    return "tavily_retrieval"


def _route_after_risk(state: TriageState) -> str:
    """Routes after risk evaluation: ask followup, interrupt, or proceed."""
    action = state.get("next_action", "")
    if action == "ask_followup":
        return "save_session"
    return "mental_health"


def _route_after_mental_health(state: TriageState) -> str:
    """Routes after mental health check."""
    return "llm_brain"


def _route_after_judge(state: TriageState) -> str:
    """Routes after judge validation."""
    return "nutrition"


def build_triage_graph() -> StateGraph:
    """
    Builds and compiles the V3 triage graph.

    Returns:
        Compiled LangGraph application ready for invocation.
    """
    graph = StateGraph(TriageState)

    # ── Register nodes ─────────────────────────────────────────────────────────
    graph.add_node("load_session", load_session_node)
    graph.add_node("symptom_extraction", symptom_extraction_node)
    graph.add_node("followup", followup_node)
    graph.add_node("tavily_retrieval", tavily_retrieval_node)
    graph.add_node("risk_evaluation", risk_evaluation_node)
    graph.add_node("mental_health", mental_health_node)
    graph.add_node("llm_brain", llm_brain_node)
    graph.add_node("judge_validator", judge_validator_node)
    graph.add_node("nutrition", nutrition_node)
    graph.add_node("ocr_processing", ocr_processing_node)
    graph.add_node("xray_analysis", xray_analysis_node)
    graph.add_node("save_session", save_session_node)

    # ── Entry point ────────────────────────────────────────────────────────────
    graph.set_entry_point("load_session")

    # ── Edges: load_session → route by input mode ──────────────────────────────
    graph.add_conditional_edges(
        "load_session",
        _route_input_mode,
        {
            "symptom_extraction": "symptom_extraction",
            "ocr_processing": "ocr_processing",
            "xray_analysis": "xray_analysis",
        },
    )

    # ── Text/voice pipeline ────────────────────────────────────────────────────
    graph.add_edge("symptom_extraction", "followup")

    graph.add_conditional_edges(
        "followup",
        _route_after_followup,
        {
            "save_session": "save_session",
            "tavily_retrieval": "tavily_retrieval",
        },
    )

    graph.add_edge("tavily_retrieval", "risk_evaluation")

    graph.add_conditional_edges(
        "risk_evaluation",
        _route_after_risk,
        {
            "save_session": "save_session",
            "mental_health": "mental_health",
        },
    )

    graph.add_edge("mental_health", "llm_brain")
    graph.add_edge("llm_brain", "judge_validator")
    graph.add_edge("judge_validator", "nutrition")
    graph.add_edge("nutrition", "save_session")

    # ── Image/X-ray pipelines → save directly ─────────────────────────────────
    graph.add_edge("ocr_processing", "save_session")
    graph.add_edge("xray_analysis", "save_session")

    # ── Terminal node ──────────────────────────────────────────────────────────
    graph.add_edge("save_session", END)

    return graph.compile()
