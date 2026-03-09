"""
xray_analysis_node.py  (Version 4)
-------------------------------------------
Processes uploaded X-ray images through the vision model pipeline.

Pipeline:
    X-ray Image → CLIP Vision Model → Structured Findings → LLaMA Explanation

V4 changes:
    - Added fallback when model returns empty results (confidence=0, labels=[]).
      Previously: empty results → no xray_findings set → llm_brain had zero context
      → hallucinated generic "cold and fever" response.
      Now: sets a clear "model unavailable" explanation so the response is honest.

Anti-hallucination:
    - Vision model provides predictions with confidence scores only.
    - LLaMA explains findings but NEVER confirms a diagnosis.
    - Mandatory radiology consultation disclaimer attached.
"""

from backend.src.tools.xray_model_tool import analyze_xray
from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("xray_analysis")

# Fallback message used when the ML model returns empty results
_XRAY_FALLBACK_MSG = (
    "🫁 X-Ray Analysis:\n\n"
    "Your X-ray image was received, but the AI screening model could not "
    "extract specific findings at this time (the model may still be loading "
    "or the image format is not supported).\n\n"
    "💡 Recommendation: Please consult a qualified radiologist for a proper "
    "review of your X-ray.\n\n"
    "⚠️ IMPORTANT: This is an AI screening tool, NOT a radiological diagnosis. "
    "These findings MUST be reviewed by a qualified radiologist before any "
    "clinical decisions."
)


def xray_analysis_node(state: TriageState) -> TriageState:
    """
    Analyzes an uploaded X-ray image and generates a patient-friendly explanation.

    Reads raw image bytes from state['image_input'] (set by xray_endpoint).
    Passes bytes to analyze_xray() which uses PIL.Image.open(io.BytesIO(...)).

    Args:
        state: Contains image_input (bytes) from the uploaded X-ray.

    Returns:
        TriageState: Updated with structured X-ray analysis in xray_findings.
    """
    image_data = state.get("image_input")

    # This node only runs when xray mode is active and image bytes are present
    if state.get("input_mode") != "xray" or not image_data:
        log_event(logger, "xray_node_skipped",
                  reason="no_image_data" if not image_data else "wrong_mode")
        return state

    # ── Step 1: Vision model classification ────────────────────────────────────
    result = analyze_xray(image_data)  # pass bytes directly

    findings = result["findings"]
    confidence = result["confidence"]
    raw_labels = result["raw_labels"]

    log_event(logger, "xray_analyzed",
              confidence=confidence,
              labels=[r["label"] for r in raw_labels])

    # ── V4 Fix: handle model failure gracefully ────────────────────────────────
    # When the model returns empty results (pipeline error / model still loading),
    # use a safe fallback instead of letting llm_brain run with zero context.
    # Without this, llm_brain defaulted to "symptoms described" which caused
    # it to hallucinate generic "cold and fever" content.
    if confidence == 0.0 and not raw_labels:
        state["xray_findings"] = _XRAY_FALLBACK_MSG
        state["image_input"] = None
        state["messages"] = state.get("messages", []) + [{
            "role": "assistant",
            "content": _XRAY_FALLBACK_MSG
        }]
        log_event(logger, "xray_fallback_used", reason="empty_model_results")
        return state

    # ── Step 2: LLaMA patient-friendly explanation ─────────────────────────────
    label_str = ", ".join(f"{r['label']} ({r['score']:.0%})" for r in raw_labels)

    prompt = (
        "You are a medical imaging assistant. Explain these X-ray findings "
        "in simple, patient-friendly language.\n\n"
        "RULES:\n"
        "- Do NOT confirm any diagnosis.\n"
        "- Do NOT use definitive language like 'You have...'.\n"
        "- Use phrases like 'The AI model suggests...', 'This may indicate...'.\n"
        "- Recommend consulting a radiologist for definitive interpretation.\n\n"
        f"Vision model findings: {label_str}\n"
        f"Raw analysis: {findings}\n\n"
        "Patient-friendly explanation (max 6 lines):"
    )

    explanation = call_llama(prompt, max_tokens=300).strip()

    if not explanation:
        explanation = findings

    explanation += (
        "\n\n⚠️ IMPORTANT: This is an AI screening tool, NOT a radiological diagnosis. "
        "These findings MUST be reviewed by a qualified radiologist before any clinical decisions."
    )

    state["xray_findings"] = explanation

    # ── Discard heavy binary data from state to prevent JSON serialization errors
    state["image_input"] = None

    # Elevate risk if concerning findings
    if confidence > 0.5 and raw_labels and raw_labels[0]["label"] != "normal chest x-ray":
        current_score = state.get("risk_score", 0.0)
        if current_score < 5.0:
            state["risk_score"] = 5.0
            state["risk_level"] = "moderate"

    # Add to conversation
    state["messages"] = state.get("messages", []) + [{
        "role": "assistant",
        "content": f"🫁 X-Ray Analysis:\n\n{explanation}"
    }]

    return state
