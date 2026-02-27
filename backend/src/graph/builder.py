"""
builder.py  (Version 5 — V5 UPGRADE)
--------------------------------------------
LangGraph workflow definition for the V5 multimodal medical triage pipeline.

# 🔥 UPGRADE V5 changes:
    1. Document image pipeline fully integrated:
       body_image → medical_vision → (if document detected) → ocr_scan
                                                             → symptom_extraction
                                                             → (medical text pipeline)
    2. Risk evaluation gates:
       risk_level == 'not_applicable'  → skip scoring (document images)
       risk_level == 'unknown'         → skip scoring (vision model failure)
       intent    == 'xray'             → skip scoring (handled by xray_analysis_node)
    3. _route_after_risk_evaluation updated to handle V5 sentinel risk levels.
    4. All routing remains deterministic — NO LLM-based routing.

Graph topology (V5):

    START
      ↓
    load_session_node
      ↓
    load_history_node
      ↓
    classification_node ─── (intent routing) ──┤
      │                                         │
      ├─ medical_text ──→ symptom_extraction    │
      │                      ↓                  │
      │                  disease_retrieval (conditional: symptoms exist)
      │                      ↓                  │
      │                  tavily_retrieval  (conditional: candidates exist)
      │                      ↓                  │
      │                  risk_evaluation (skips if not_applicable/unknown) │
      │                      ↓                  │
      │                  svm_analysis           │
      │                      ↓                  │
      ├──────────────────→ llm_brain ←───────────┤
      │                      ↓                  │
      ├─ medical_report ─→ ocr_scan             │
      │                      ↓                  │
      │                  symptom_extraction      │
      │                      ↓                  │
      │                  (→ medical text pipeline continues)
      │                                         │
      ├─ xray ────────→ xray_analysis         │
      │                      ↓                  │
      │                  risk_evaluation (skipped for xray) │
      │                      ↓                  │
      │                  llm_brain               │
      │                                         │
      ├─ body_image ───→ medical_vision         │
      │                  ├─ body/skin → llm_brain │
      │                  └─ document  → ocr_scan (🔥 V5: document redirect)
      │                                ↓
      │                       symptom_extraction
      │                                ↓
      │                       (medical text pipeline)
      │
      └─ casual ──────→ mental_health
                             ↓
                         llm_brain
                             ↓
                      judge_validator
                         ↓ (conditional)
                    ┌─ PASS → nutrition (conditional) → response_node
                    └─ FAIL → llm_brain (max 2 retries)
                                    ↓
                              response_node
                                    ↓
                              save_history_node
                                    ↓
                              save_session_node
                                    ↓
                                   END

Performance rules:
    - Heavy nodes (OCR, Vision, Tavily, Disease Retrieval) behind conditional edges.
    - No Tavily/Disease Retrieval in vision-only flows.
    - No OCR/X-ray in text-only queries.
    - Early intent classification minimizes graph traversal.
    - Max recursion_limit = 25.
    - Judge regeneration capped at 2 attempts.
    - Risk evaluation skipped for non-scoreable intents/states (🔥 V5).
"""

from langgraph.graph import StateGraph, END

from backend.src.state.state import TriageState

# ── Node imports ─────────────────────────────────────────────────────────────
from backend.src.nodes.load_session_node import load_session_node
from backend.src.nodes.load_history_node import load_history_node
from backend.src.nodes.classification_node import classification_node
from backend.src.nodes.symptom_extraction_node import symptom_extraction_node
from backend.src.nodes.disease_retrieval_node import disease_retrieval_node
from backend.src.nodes.tavily_retrieval_node import tavily_retrieval_node
from backend.src.nodes.risk_evaluation_node import risk_evaluation_node
from backend.src.nodes.svm_analysis_node import svm_analysis_node
from backend.src.nodes.mental_health_node import mental_health_node
from backend.src.nodes.llm_brain_node import llm_brain_node
from backend.src.nodes.judge_validator_node import judge_validator_node
from backend.src.nodes.nutrition_node import nutrition_node
from backend.src.nodes.response_node import response_node
from backend.src.nodes.medical_vision_node import medical_vision_node
from backend.src.nodes.ocr_processing_node import ocr_scan_node
from backend.src.nodes.xray_analysis_node import xray_analysis_node
from backend.src.nodes.save_history_node import save_history_node
from backend.src.nodes.save_session_node import save_session_node


# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTING FUNCTIONS (Deterministic, no LLM)
# ═══════════════════════════════════════════════════════════════════════════════


def _route_by_intent(state: TriageState) -> str:
    """
    Routes to the correct pipeline based on intent classification.

    Returns graph node name to execute next.
    """
    intent = state.get("intent", "medical_text")
    return {
        "medical_text":   "symptom_extraction",
        "medical_report": "ocr_scan",
        "xray":           "xray_analysis",
        "body_image":     "medical_vision",
        "casual":         "mental_health",
    }.get(intent, "symptom_extraction")


def _route_after_risk_evaluation(state: TriageState) -> str:
    """
    Routes after risk evaluation:
    - Text-based intents (medical_text, medical_report) → svm_analysis
    - Vision-based intents (xray) → skip svm, go directly to llm_brain
    - # 🔥 UPGRADE V5: sentinel risk levels → skip svm, go to llm_brain
      risk_level == 'not_applicable' (document) → llm_brain
      risk_level == 'unknown'        (fail)      → llm_brain
      These states already have their risk_level set; svm_analysis cannot
      improve the score and would introduce latency for no benefit.
    """
    intent     = state.get("intent", "medical_text")
    risk_level = state.get("risk_level", "").lower()

    # 🔥 UPGRADE V5: sentinel levels bypass svm_analysis
    if risk_level in ("not_applicable", "unknown"):
        return "llm_brain"

    if intent in ("medical_text", "medical_report"):
        return "svm_analysis"
    return "llm_brain"


def _route_after_symptom_extraction(state: TriageState) -> str:
    """
    Routes after symptom extraction:
    - If symptoms exist → disease_retrieval (vector store lookup)
    - If no symptoms → skip to risk_evaluation (fallback)
    """
    symptoms = state.get("symptoms", [])
    if symptoms:
        return "disease_retrieval"
    return "risk_evaluation"


def _route_after_disease_retrieval(state: TriageState) -> str:
    """
    Routes after disease retrieval:
    - If candidates found → tavily_retrieval (grounded web search)
    - If no candidates → skip to risk_evaluation
    """
    candidates = state.get("disease_candidates", [])
    retrieved = state.get("retrieved_info", [])
    if candidates or retrieved:
        return "tavily_retrieval"
    return "risk_evaluation"


def _route_after_judge(state: TriageState) -> str:
    """
    Routes after judge validation:
    - PASS → check if nutrition image is needed
    - FAIL + retries left → back to llm_brain for regeneration
    - FAIL + max retries (force_accepted) → proceed to nutrition check

    This implements the max-2-retry loop.
    """
    judge_passed = state.get("judge_passed", False)
    force_accepted = state.get("force_accepted", False)

    if judge_passed or force_accepted:
        return _route_nutrition_check(state)

    # Judge failed — check regeneration budget
    regen_count = state.get("regeneration_count", 0)
    if regen_count < 2:
        return "llm_brain"

    # Exhausted retries — force proceed
    return _route_nutrition_check(state)


def _route_nutrition_check(state: TriageState) -> str:
    """
    Determines whether to run nutrition_node before response_node.
    """
    needs_nutrition = state.get("needs_nutrition_image", False)
    risk_level = state.get("risk_level", "").lower()

    if needs_nutrition and risk_level in ("low", "moderate"):
        return "nutrition"
    return "response"


def _route_after_vision(state: TriageState) -> str:
    """
    # 🔥 V5 DOCUMENT PIPELINE UPGRADE: Renamed from _route_after_medical_vision.

    Routes after medical_vision_node with two-layer deterministic signal:

    PRIMARY check — state["is_document"] (V5 explicit flag):
        True  → ocr_scan (document mode: image requires OCR → text pipeline)

    FALLBACK check — state["intent"] == 'medical_report' (V4.1 compat):
        Handles edge case where is_document wasn't set but intent was updated.
        → ocr_scan

    DEFAULT:
        → llm_brain (body/skin images proceed to reasoning directly)

    Guarantees deterministic routing — no LLM involved.
    """
    # 🔥 V5 DOCUMENT PIPELINE UPGRADE: primary signal — explicit is_document flag
    if state.get("is_document"):
        return "ocr_scan"
    # Fallback: intent-based signal (V4.1 compat, handles partial state writes)
    if state.get("intent", "body_image") == "medical_report":
        return "ocr_scan"
    return "llm_brain"


def _route_after_save_history(state: TriageState) -> str:
    """
    Routes after save_history:
    - Normal flow → save_session → END
    - Follow-up interrupt → skip saving, go to END (handled by save_session)
    """
    return "save_session"


# ═══════════════════════════════════════════════════════════════════════════════
#  GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════════════════


def build_triage_graph() -> StateGraph:
    """
    Builds and compiles the V5 multimodal triage graph.

    # 🔥 UPGRADE V5 architecture principles:
        - Deterministic routing via conditional edges (NO LLM-based routing)
        - Document images route through OCR → medical text pipeline
        - Risk evaluation skipped for not_applicable/unknown sentinel states
        - Heavy nodes behind guards (OCR, Vision, Tavily, Disease Retrieval)
        - Max recursion_limit = 25
        - Judge regeneration capped at 2 loops
        - Response formatting separated from LLM reasoning
        - History saving only after completed interactions

    Returns:
        Compiled LangGraph application ready for invocation.
    """
    graph = StateGraph(TriageState)

    # ═══════════════════════════════════════════════════════════════════════════
    #  NODE REGISTRATION
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Entry chain ──────────────────────────────────────────────────────────
    graph.add_node("load_session",        load_session_node)
    graph.add_node("load_history",        load_history_node)
    graph.add_node("classification",      classification_node)

    # ── Medical text pipeline ────────────────────────────────────────────────
    graph.add_node("symptom_extraction",  symptom_extraction_node)
    graph.add_node("disease_retrieval",   disease_retrieval_node)
    graph.add_node("tavily_retrieval",    tavily_retrieval_node)
    graph.add_node("risk_evaluation",     risk_evaluation_node)
    graph.add_node("svm_analysis",        svm_analysis_node)

    # ── Vision pipelines ─────────────────────────────────────────────────────
    graph.add_node("ocr_scan",           ocr_scan_node)
    graph.add_node("xray_analysis",      xray_analysis_node)
    graph.add_node("medical_vision",     medical_vision_node)

    # ── Mental / casual pipeline ─────────────────────────────────────────────
    graph.add_node("mental_health",      mental_health_node)

    # ── Reasoning & validation ───────────────────────────────────────────────
    graph.add_node("llm_brain",          llm_brain_node)
    graph.add_node("judge_validator",    judge_validator_node)

    # ── Post-reasoning ───────────────────────────────────────────────────────
    graph.add_node("nutrition",          nutrition_node)
    graph.add_node("response",           response_node)

    # ── Persistence ──────────────────────────────────────────────────────────
    graph.add_node("save_history",       save_history_node)
    graph.add_node("save_session",       save_session_node)

    # ═══════════════════════════════════════════════════════════════════════════
    #  EDGE DEFINITIONS
    # ═══════════════════════════════════════════════════════════════════════════

    # ── STEP 1: Entry chain (sequential) ─────────────────────────────────────
    # START → load_session → load_history → classification
    graph.set_entry_point("load_session")
    graph.add_edge("load_session", "load_history")
    graph.add_edge("load_history", "classification")

    # ── STEP 2: Intent routing (conditional) ─────────────────────────────────
    graph.add_conditional_edges(
        "classification",
        _route_by_intent,
        {
            "symptom_extraction": "symptom_extraction",
            "ocr_scan":           "ocr_scan",
            "xray_analysis":      "xray_analysis",
            "medical_vision":     "medical_vision",
            "mental_health":      "mental_health",
        },
    )

    # ── STEP 3: Medical text pipeline ────────────────────────────────────────
    # symptom_extraction → disease_retrieval (if symptoms) → tavily (if candidates)
    #                   → risk_evaluation → svm_analysis → llm_brain
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

    # Conditional: text intents → svm_analysis, vision intents → llm_brain directly
    graph.add_conditional_edges(
        "risk_evaluation",
        _route_after_risk_evaluation,
        {
            "svm_analysis": "svm_analysis",
            "llm_brain":    "llm_brain",
        },
    )

    graph.add_edge("svm_analysis",     "llm_brain")

    # ── STEP 4: Medical report pipeline ──────────────────────────────────────
    # ocr_scan → symptom_extraction (continues through text pipeline)
    graph.add_edge("ocr_scan", "symptom_extraction")

    # ── STEP 5: X-ray pipeline ───────────────────────────────────────────────
    # xray_analysis → risk_evaluation → llm_brain (skips svm_analysis)
    graph.add_edge("xray_analysis", "risk_evaluation")

    # ── STEP 6: Body image pipeline ─────────────────────────────────────────────
    # medical_vision → llm_brain (body/skin images)
    #              ↘ ocr_scan (if vision detected a document — 🔥 V5 primary: is_document flag)
    graph.add_conditional_edges(
        "medical_vision",
        _route_after_vision,    # 🔥 V5 DOCUMENT PIPELINE UPGRADE: renamed from _route_after_medical_vision
        {
            "llm_brain": "llm_brain",
            "ocr_scan":  "ocr_scan",
        },
    )

    # ── STEP 7: Casual / mental health pipeline ──────────────────────────────
    # mental_health → llm_brain
    graph.add_edge("mental_health", "llm_brain")

    # ── STEP 8: Post-reasoning chain ─────────────────────────────────────────
    # llm_brain → judge_validator → (conditional routing)
    graph.add_edge("llm_brain", "judge_validator")

    graph.add_conditional_edges(
        "judge_validator",
        _route_after_judge,
        {
            "llm_brain":  "llm_brain",    # Regeneration loop (max 2)
            "nutrition":  "nutrition",     # Nutrition image needed
            "response":   "response",     # Direct to response
        },
    )

    # ── STEP 9-10: Nutrition → Response ──────────────────────────────────────
    graph.add_edge("nutrition", "response")

    # ── STEP 11: Persistence chain ───────────────────────────────────────────
    # response → save_history → save_session → END
    graph.add_edge("response",     "save_history")
    graph.add_edge("save_history", "save_session")
    graph.add_edge("save_session", END)

    # ═══════════════════════════════════════════════════════════════════════════
    #  COMPILE
    # ═══════════════════════════════════════════════════════════════════════════

    return graph.compile()
