"""
builder.py  (Version 6 — FINAL ARCHITECTURE)
----------------------------------------------
LangGraph workflow definition for the V6 multimodal medical triage pipeline.

V6 topology (FINAL — DO NOT EXTEND):

    START
      ↓
    load_session
      ↓
    speech_to_text          (voice input only; passes through for text/image)
      ↓
    load_history
      ↓
    classification           (deterministic, no LLM)
      ↓
    Intent routing ─────────────────────────────────────────────────┐
      │                                                              │
      ├─ medical_text   → symptom_extraction                        │
      │                      ↓ (if symptoms)                        │
      │                  disease_retrieval                          │
      │                      ↓ (if candidates)                      │
      │                  tavily_retrieval                           │
      │                      ↓                                      │
      │                  risk_evaluation                            │
      │                                                              │
      ├─ medical_report → ocr_scan → symptom_extraction → (above)  │
      │                                                              │
      ├─ xray           → xray_analysis → risk_evaluation           │
      │                                                              │
      ├─ body_image     → medical_vision                            │
      │                      ├─ document → ocr_scan (above)         │
      │                      └─ body/skin → risk_evaluation         │
      │                                                              │
      └─ casual         → risk_evaluation (minimal path)            │
                                                                     │
    ◄────────────────────────────────────────────────────────────────┘
      ↓
    red_flag_engine          (config-driven, no LLM)
      ↓
    context_synthesizer      (pure string merge, no LLM)
      ↓
    llm_brain                (structured JSON output)
      ↓
    judge_validator          (max 2 retries)
      ↓ (conditional)
    ┌─ PASS → nutrition (if low/moderate) → response
    └─ FAIL (≥2 attempts) → response directly
      ↓
    response                 (deterministic tone + system_trace)
      ↓
    async_nutrition_image    (non-blocking image gen — fires after text is ready)
      ↓
    emergency_escalation     (Twilio, all 5 guards required)
      ↓
    text_to_speech           (voice output, guarded by voice_response_required)
      ↓
    save_history
      ↓
    save_session
      ↓
    END

Non-negotiable rules:
    - No LLM-based routing.
    - No dynamic planning.
    - No agent swarms.
    - recursion_limit = 25.
    - Judge regeneration cap = 2.
    - Heavy nodes behind conditional guards.
"""

from langgraph.graph import StateGraph, END

from backend.src.state.state import TriageState

# ── Node imports ─────────────────────────────────────────────────────────────
from backend.src.nodes.load_session_node           import load_session_node
from backend.src.nodes.speech_to_text_node         import speech_to_text_node
from backend.src.nodes.load_history_node           import load_history_node
from backend.src.nodes.classification_node         import classification_node
from backend.src.nodes.symptom_extraction_node     import symptom_extraction_node
from backend.src.nodes.disease_retrieval_node      import disease_retrieval_node
from backend.src.nodes.tavily_retrieval_node       import tavily_retrieval_node
from backend.src.nodes.risk_evaluation_node        import risk_evaluation_node
from backend.src.nodes.red_flag_engine_node        import red_flag_engine_node
from backend.src.nodes.context_synthesizer_node    import context_synthesizer_node
from backend.src.nodes.medical_vision_node         import medical_vision_node
from backend.src.nodes.ocr_processing_node         import ocr_scan_node
from backend.src.nodes.xray_analysis_node          import xray_analysis_node
from backend.src.nodes.llm_brain_node              import llm_brain_node
from backend.src.nodes.judge_validator_node        import judge_validator_node
from backend.src.nodes.nutrition_node                  import nutrition_node
from backend.src.nodes.async_nutrition_image_node      import async_nutrition_image_node
from backend.src.nodes.response_node                   import response_node
from backend.src.nodes.emergency_escalation_node   import emergency_escalation_node
from backend.src.nodes.text_to_speech_node         import text_to_speech_node
from backend.src.nodes.save_history_node           import save_history_node
from backend.src.nodes.save_session_node           import save_session_node


# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTING FUNCTIONS (Deterministic — NO LLM)
# ═══════════════════════════════════════════════════════════════════════════════


def _route_by_intent(state: TriageState) -> str:
    """
    Routes to the correct pipeline entry point based on classification result.
    Returns a graph node name.
    """
    return {
        "medical_text":   "symptom_extraction",
        "medical_report": "ocr_scan",
        "xray":           "xray_analysis",
        "body_image":     "medical_vision",
        "casual":         "risk_evaluation",   # casual: skip symptom/retrieval, go direct
    }.get(state.get("intent", "medical_text"), "symptom_extraction")


def _route_after_symptom_extraction(state: TriageState) -> str:
    """
    Routes to disease_retrieval if symptoms found, else skips to risk_evaluation.
    Guard: heavy node only runs when symptoms exist.
    """
    return "disease_retrieval" if state.get("symptoms") else "risk_evaluation"


def _route_after_disease_retrieval(state: TriageState) -> str:
    """
    Routes to tavily_retrieval if disease candidates found, else skips.
    Guard: Tavily only runs when vector store found candidates.
    """
    if state.get("disease_candidates") or state.get("retrieved_info"):
        return "tavily_retrieval"
    return "risk_evaluation"


def _route_after_vision(state: TriageState) -> str:
    """
    Routes after medical_vision_node:
    - Document detected (is_document flag or medical_report redirect) → ocr_scan
    - Body/skin image → risk_evaluation
    """
    if state.get("is_document"):
        return "ocr_scan"
    if state.get("intent", "") == "medical_report":
        return "ocr_scan"
    return "risk_evaluation"


def _route_after_risk_evaluation(state: TriageState) -> str:
    """
    All paths converge at risk_evaluation and proceed to red_flag_engine.
    No branching here — simplified in V6.
    """
    return "red_flag_engine"


def _route_after_judge(state: TriageState) -> str:
    """
    Routes after judge validation.
    NOTE: Sequential LLM calls (llm_brain -> judge -> nutrition) increase latency,
    but user constraint explicitly forbids moving nutrition before judge.
    """
    judge_passed   = state.get("judge_passed", False)
    force_accepted = state.get("force_accepted", False)

    if judge_passed or force_accepted:
        return _route_nutrition_check(state)

    regen = state.get("regeneration_count", 0)
    return "llm_brain" if regen < 2 else _route_nutrition_check(state)


def _route_nutrition_check(state: TriageState) -> str:
    if (
        state.get("trigger_nutrition_node") is True
        and state.get("risk_level") in ("low", "moderate")
        and state.get("urgency") != "emergency"
        and not state.get("red_flag_triggered", False)
    ):
        return "nutrition"

    return "response"


# ═══════════════════════════════════════════════════════════════════════════════
#  GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════════════════


def build_triage_graph() -> StateGraph:
    """
    Builds and compiles the V6 final triage graph.

    Returns:
        Compiled LangGraph application (recursion_limit=25).
    """
    graph = StateGraph(TriageState)

    # ── Node registration ──────────────────────────────────────────────────────
    graph.add_node("load_session",         load_session_node)
    graph.add_node("speech_to_text",       speech_to_text_node)
    graph.add_node("load_history",         load_history_node)
    graph.add_node("classification",       classification_node)

    # Medical text pipeline
    graph.add_node("symptom_extraction",   symptom_extraction_node)
    graph.add_node("disease_retrieval",    disease_retrieval_node)
    graph.add_node("tavily_retrieval",     tavily_retrieval_node)

    # Vision pipelines
    graph.add_node("medical_vision",       medical_vision_node)
    graph.add_node("ocr_scan",             ocr_scan_node)
    graph.add_node("xray_analysis",        xray_analysis_node)

    # Risk + red flag
    graph.add_node("risk_evaluation",      risk_evaluation_node)
    graph.add_node("red_flag_engine",      red_flag_engine_node)
    graph.add_node("context_synthesizer",  context_synthesizer_node)

    # Reasoning + validation
    graph.add_node("llm_brain",            llm_brain_node)
    graph.add_node("judge_validator",      judge_validator_node)

    # Post-reasoning
    graph.add_node("nutrition",               nutrition_node)
    graph.add_node("response",                response_node)
    graph.add_node("async_nutrition_image",   async_nutrition_image_node)
    graph.add_node("emergency_escalation",    emergency_escalation_node)
    graph.add_node("text_to_speech",       text_to_speech_node)

    # Persistence
    graph.add_node("save_history",         save_history_node)
    graph.add_node("save_session",         save_session_node)

    # ── Edge definitions ───────────────────────────────────────────────────────

    # STEP 1: Entry chain
    graph.set_entry_point("load_session")
    graph.add_edge("load_session",       "speech_to_text")
    graph.add_edge("speech_to_text",     "load_history")
    graph.add_edge("load_history",       "classification")

    # STEP 2: Intent routing
    graph.add_conditional_edges(
        "classification",
        _route_by_intent,
        {
            "symptom_extraction": "symptom_extraction",
            "ocr_scan":           "ocr_scan",
            "xray_analysis":      "xray_analysis",
            "medical_vision":     "medical_vision",
            "risk_evaluation":    "risk_evaluation",
        },
    )

    # STEP 3: Medical text pipeline
    graph.add_conditional_edges(
        "symptom_extraction",
        _route_after_symptom_extraction,
        {
            "disease_retrieval": "disease_retrieval",
            "risk_evaluation":   "risk_evaluation",
        },
    )

    graph.add_conditional_edges(
        "disease_retrieval",
        _route_after_disease_retrieval,
        {
            "tavily_retrieval": "tavily_retrieval",
            "risk_evaluation":  "risk_evaluation",
        },
    )

    graph.add_edge("tavily_retrieval", "risk_evaluation")

    # STEP 4: OCR → text pipeline
    graph.add_edge("ocr_scan", "symptom_extraction")

    # STEP 5: X-ray pipeline
    graph.add_edge("xray_analysis", "risk_evaluation")

    # STEP 6: Body image pipeline
    graph.add_conditional_edges(
        "medical_vision",
        _route_after_vision,
        {
            "ocr_scan":        "ocr_scan",
            "risk_evaluation": "risk_evaluation",
        },
    )

    # STEP 7: Risk evaluation → red flag → context synthesizer → llm_brain
    graph.add_edge("risk_evaluation",     "red_flag_engine")
    graph.add_edge("red_flag_engine",     "context_synthesizer")
    graph.add_edge("context_synthesizer", "llm_brain")

    # STEP 8: Post-reasoning chain
    graph.add_edge("llm_brain", "judge_validator")

    graph.add_conditional_edges(
        "judge_validator",
        _route_after_judge,
        {
            "llm_brain": "llm_brain",
            "nutrition":  "nutrition",
            "response":   "response",
        },
    )

    graph.add_edge("nutrition", "response")

    # STEP 9: Post-response pipeline
    graph.add_edge("response",               "async_nutrition_image")
    graph.add_edge("async_nutrition_image",  "emergency_escalation")
    graph.add_edge("emergency_escalation",   "text_to_speech")
    graph.add_edge("text_to_speech",       "save_history")
    graph.add_edge("save_history",         "save_session")
    graph.add_edge("save_session",         END)

    return graph.compile()
