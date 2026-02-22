"""
xray_analysis_node.py  (Version 3 — NEW)
-------------------------------------------
Processes uploaded X-ray images through the vision model pipeline.

Pipeline:
    X-ray Image → CLIP Vision Model → Structured Findings → LLaMA Explanation

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


def xray_analysis_node(state: TriageState) -> TriageState:
    """
    Analyzes an uploaded X-ray image and generates a patient-friendly explanation.

    Args:
        state: Contains xray_findings (as file path if xray mode).

    Returns:
        TriageState: Updated with structured X-ray analysis.
    """
    image_path = state.get("xray_findings", "")

    # This node only runs for xray mode
    if state.get("input_mode") != "xray" or not image_path:
        return state

    # ── Step 1: Vision model classification ────────────────────────────────────
    result = analyze_xray(image_path)

    findings = result["findings"]
    confidence = result["confidence"]
    raw_labels = result["raw_labels"]

    log_event(logger, "xray_analyzed",
              confidence=confidence,
              labels=[r["label"] for r in raw_labels])

    # ── Step 2: LLaMA patient-friendly explanation ─────────────────────────────
    label_str = ", ".join(f"{r['label']} ({r['score']:.0%})" for r in raw_labels)

    prompt = (
        "You are a medical imaging assistant. Explain these chest X-ray findings "
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

    # Elevate risk if concerning findings
    if confidence > 0.5 and raw_labels and raw_labels[0]["label"] != "normal chest x-ray":
        current_score = state.get("risk_score", 0.0)
        if current_score < 5.0:
            state["risk_score"] = 5.0
            state["risk_level"] = "moderate"

    # Add to conversation
    state["messages"].append({
        "role": "assistant",
        "content": f"🫁 X-Ray Analysis:\n\n{explanation}"
    })

    return state
