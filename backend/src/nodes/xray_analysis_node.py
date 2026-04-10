"""
xray_analysis_node.py  (Version 5 — Modality-Aware, Region-Restricted)
-----------------------------------------------------------------------
Processes uploaded X-ray images through the vision model pipeline.

V5 changes (CRITICAL FIXES):
    - MODALITY-AWARE: Detects the body region from the image label/metadata.
    - REGION-RESTRICTED: Prompt explicitly limits analysis to the detected region.
      e.g., leg X-ray → ONLY discusses bones/joints of that leg.
      NEVER mentions unrelated regions (no "heart is fine" on a leg X-ray).
    - CALM TONE: Removed alarming language. Critical findings described calmly.
    - User-friendly: No medical jargon in the patient-facing explanation.
    - All V4 fallbacks preserved.
"""

from backend.src.tools.xray_model_tool import analyze_xray
from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("xray_analysis")

# Fallback when model returns empty results
_XRAY_FALLBACK_MSG = (
    "Thanks for sharing your X-ray.\n\n"
    "The scan isn't clear enough for an automated review right now — "
    "this is normal and can happen with image quality or angle.\n\n"
    "A doctor looking at this directly will give you a much more accurate picture.\n\n"
    "*TriGuard is a screening aid — not a diagnosis. Please consult a qualified doctor.*"
)

# Region detection keywords → label for the LLM prompt
_REGION_KEYWORDS = {
    "chest":      "chest (lungs and ribcage area only)",
    "lung":       "chest (lungs and ribcage area only)",
    "heart":      "chest (heart and surrounding structures only)",
    "hand":       "hand and wrist bones and joints only",
    "wrist":      "wrist bones and joints only",
    "knee":       "knee joint and surrounding bones only",
    "leg":        "leg bones and joints only",
    "foot":       "foot bones and toe joints only",
    "ankle":      "ankle joint and surrounding bones only",
    "hip":        "hip joint and pelvis area only",
    "spine":      "spine (vertebral column) only",
    "neck":       "cervical spine (neck region) only",
    "shoulder":   "shoulder joint and surrounding bones only",
    "elbow":      "elbow joint and surrounding bones only",
    "skull":      "skull bones only",
    "abdomen":    "abdominal region only",
    "pelvis":     "pelvis and hip bones only",
    "rib":        "ribcage area only",
    "arm":        "arm bones and joints only",
    "forearm":    "forearm bones (radius and ulna) only",
}


def _detect_region(labels: list) -> str:
    """
    Detects the body region from model output labels.
    Returns a human-readable region string for the prompt.
    """
    combined = " ".join(str(lbl.get("label", "")) for lbl in labels).lower()
    for keyword, region in _REGION_KEYWORDS.items():
        if keyword in combined:
            return region
    return "the visible area in this X-ray only"  # safe default


def xray_analysis_node(state: TriageState) -> TriageState:
    """
    Analyzes an uploaded X-ray image and generates a modality-restricted,
    region-specific patient-friendly explanation.

    Args:
        state: Contains image_input (bytes) from the uploaded X-ray.

    Returns:
        TriageState: Updated with structured X-ray analysis in xray_findings.
    """
    image_data = state.get("image_input")

    if state.get("input_mode") != "xray" or not image_data:
        log_event(logger, "xray_node_skipped",
                  reason="no_image_data" if not image_data else "wrong_mode")
        return state

    # ── Step 1: Vision model classification ──────────────────────────────────
    result = analyze_xray(image_data)

    findings   = result["findings"]
    confidence = result["confidence"]
    raw_labels = result["raw_labels"]

    log_event(logger, "xray_analyzed",
              confidence=confidence,
              labels=[r["label"] for r in raw_labels])

    # ── Fallback: model returned nothing useful ───────────────────────────────
    if confidence == 0.0 and not raw_labels:
        state["xray_findings"] = _XRAY_FALLBACK_MSG
        state["image_input"]   = None
        state["messages"].append({"role": "assistant", "content": _XRAY_FALLBACK_MSG})
        log_event(logger, "xray_fallback_used", reason="empty_model_results")
        return state

    # ── Step 2: Detect the body region from labels ────────────────────────────
    body_region = _detect_region(raw_labels)

    # ── Step 3: LLaMA region-restricted explanation ───────────────────────────
    label_str = ", ".join(f"{r['label']} ({r['score']:.0%})" for r in raw_labels)

    prompt = (
        "You are TriGuard AI — a warm, calm health assistant helping a non-medical person "
        "understand their X-ray screening result.\n\n"
        f"CRITICAL RULE: You MUST discuss ONLY {body_region}. "
        "Do NOT mention any other organ, body part, or region that is not visible in this X-ray.\n\n"
        "Follow these rules:\n"
        "1. Start with what looks reassuring if anything looks normal.\n"
        "2. Use simple, everyday language. NO heavy medical jargon.\n"
        "3. If the model detected a fracture, break, or crack — state it clearly but calmly. "
        "   Say 'it looks like there may be a break or crack in [bone]' — do NOT hide important findings.\n"
        "4. Keep the response under 150 words.\n"
        "5. End with ONE clear, calm recommendation — e.g. 'Please see a doctor today'.\n"
        "6. Tone: like a caring friend explaining a picture, not a medical report.\n"
        "7. NEVER mention organs or body parts outside the detected region.\n"
        "8. Do NOT confirm a diagnosis with certainty. Use 'it appears', 'it looks like'.\n\n"
        f"X-ray region detected: {body_region}\n"
        f"Model findings: {label_str}\n"
        f"Raw analysis: {findings}\n\n"
        "Write only the patient-friendly message:"
    )

    explanation = call_llama(prompt, max_tokens=350).strip()

    if not explanation:
        explanation = findings

    # Format as section-based response
    explanation = (
        f"### 🩻 X-Ray Review — {body_region.split(' ')[0].title()}\n\n"
        f"{explanation}\n\n"
        "---\n\n"
        "*TriGuard is a screening aid — not a diagnosis. Please consult a qualified doctor.*"
    )

    state["xray_findings"] = explanation
    state["image_input"]   = None

    # Elevate risk appropriately for fractures and high-confidence findings
    if confidence > 0.5 and raw_labels and raw_labels[0]["label"] != "normal":
        label_lower = raw_labels[0]["label"].lower()
        is_fracture = any(kw in label_lower for kw in ("fracture", "break", "crack", "fibula", "tibia"))
        if is_fracture or confidence > 0.8:
            state["risk_score"] = 7.0
            state["risk_level"] = "high"
        else:
            current_score = state.get("risk_score", 0.0)
            if current_score < 5.0:
                state["risk_score"] = 5.0
                state["risk_level"] = "moderate"

    state["messages"].append({"role": "assistant", "content": explanation})
    return state
