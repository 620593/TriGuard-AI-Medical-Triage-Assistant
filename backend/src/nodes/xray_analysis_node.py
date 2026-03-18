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
    "Thanks for sharing your X-ray. From this quick screen, many parts are not "
    "clear enough to explain confidently yet.\n\n"
    "A doctor can take a closer look and guide you with the right next step.\n\n"
    "TriGuard is a screening aid, not a diagnosis. Please consult a qualified "
    "doctor for medical advice."
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
        state["messages"].append({
            "role": "assistant",
            "content": _XRAY_FALLBACK_MSG
        })
        log_event(logger, "xray_fallback_used", reason="empty_model_results")
        return state

    # ── Step 2: LLaMA patient-friendly explanation ─────────────────────────────
    label_str = ", ".join(f"{r['label']} ({r['score']:.0%})" for r in raw_labels)

    prompt = (
        "You are a warm, calm health assistant helping a non-medical person understand "
        "their chest X-ray screening result. Follow these rules strictly:\n\n"
        "1. Start with reassurance: mention what appears normal first.\n"
        "2. Use simple everyday language only. No medical jargon whatsoever.\n"
        "3. If something needs attention, say 'there's an area worth having a doctor "
        "look at' - never say 'abnormal finding' or 'pathology detected'.\n"
        "4. Keep the response under 120 words total.\n"
        "5. End with ONE clear, calm next step - not a list of scary bullet points.\n"
        "6. Tone: like a caring friend, not a medical report.\n"
        "7. Never use words: fracture, lesion, opacity, infiltrate, consolidation, "
        "abnormality, critical, MUST, immediately (unless truly life-threatening).\n"
        "8. The disclaimer must be one gentle line at the bottom, not bold or alarming.\n"
        "9. Do not confirm a diagnosis and do not use 'you have'.\n\n"
        f"Vision model findings: {label_str}\n"
        f"Raw analysis: {findings}\n\n"
        "Return only the final patient message text."
    )

    explanation = call_llama(prompt, max_tokens=300).strip()

    if not explanation:
        explanation = findings

    explanation += (
        "\n\nTriGuard is a screening aid, not a diagnosis. "
        "Please consult a qualified doctor for medical advice."
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
    state["messages"].append({
        "role": "assistant",
        "content": explanation
    })

    return state
