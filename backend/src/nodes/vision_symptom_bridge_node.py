"""
vision_symptom_bridge_node.py
------------------------------
Bridges the vision pipeline (body_image / xray) into the symptom-based
medical pipeline so BOTH image types receive the full treatment:
  symptom extraction → disease retrieval → risk evaluation → 7-section card.

For body/skin images:
    - Reads vision_findings["visual_findings"], ["possible_conditions"],
      ["lesion_morphology"], ["distribution"]
    - Converts them into a flat symptom list (e.g. ["rash", "redness", "blisters"])
    - Stores in state["symptoms"] so disease_retrieval can look them up

For X-ray images:
    - Reads xray_findings (raw text from xray_analysis_node)
    - Reads raw_labels/findings from xray_analysis via vision metadata
    - Converts detected labels into symptom-like terms
    - Forces state["symptoms"] so disease_retrieval can find relevant conditions

Both paths skip followup_check (images don't need clarification questions).
Sets state["user_input"] to a contextual summary so llm_brain has rich context.
"""

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("vision_bridge")

# ── Skin/body image term mapping ───────────────────────────────────────────────
# Map common vision output terms → medical symptom terms disease_retrieval knows

_SKIN_TERM_MAP = {
    "redness":         "redness",
    "red":             "redness",
    "inflamed":        "inflammation",
    "inflammation":    "inflammation",
    "rash":            "rash",
    "bumps":           "skin bumps",
    "blisters":        "blisters",
    "blister":         "blisters",
    "pustules":        "pustules",
    "swelling":        "swelling",
    "hives":           "hives",
    "urticaria":       "hives",
    "eczema":          "eczema",
    "dermatitis":      "dermatitis",
    "psoriasis":       "psoriasis",
    "itching":         "itching",
    "itchy":           "itching",
    "dry skin":        "dry skin",
    "scaly":           "scaly skin",
    "flaking":         "flaking skin",
    "lesion":          "skin lesion",
    "patch":           "skin patch",
    "spots":           "skin spots",
    "dark spots":      "pigmentation",
    "pigmentation":    "pigmentation",
    "bleeding":        "bleeding",
    "crusting":        "crusting",
    "discharge":       "skin discharge",
    "wound":           "wound",
    "infection":       "skin infection",
    "fungal":          "fungal infection",
    "ringworm":        "ringworm",
    "acne":            "acne",
    "pimples":         "acne",
}

# ── X-ray label → symptom term mapping ────────────────────────────────────────

_XRAY_TERM_MAP = {
    "fracture":            "bone fracture",
    "fractured":           "bone fracture",
    "break":               "bone fracture",
    "crack":               "bone fracture",
    "fibula":              "fibula injury",
    "tibia":               "tibia injury",
    "femur":               "femur injury",
    "radius":              "forearm fracture",
    "ulna":                "forearm fracture",
    "humerus":             "arm fracture",
    "spine":               "spinal injury",
    "vertebra":            "vertebral injury",
    "disc":                "disc injury",
    "pneumonia":           "pneumonia",
    "consolidation":       "lung consolidation",
    "effusion":            "pleural effusion",
    "cardiomegaly":        "enlarged heart",
    "pneumothorax":        "pneumothorax",
    "edema":               "pulmonary edema",
    "mass":                "lung mass",
    "nodule":              "lung nodule",
    "arthritis":           "arthritis",
    "osteoporosis":        "osteoporosis",
    "dislocation":         "dislocation",
    "joint":               "joint abnormality",
    "normal":              None,   # skip normal findings
}


def _extract_skin_symptoms(vision: dict) -> list[str]:
    """
    Extracts a meaningful symptom list from vision_findings for body/skin images.
    Combines: visual_findings, possible_conditions, lesion_morphology, distribution.
    """
    symptoms = set()
    combined_text = ""

    # From visual_findings list (e.g. ["small bumps", "redness", "blisters"])
    for finding in vision.get("visual_findings", []):
        combined_text += " " + str(finding).lower()

    # From possible_conditions (e.g. ["urticaria", "eczema", "dermatitis"])
    for cond in vision.get("possible_conditions", []):
        cond_lower = str(cond).lower()
        combined_text += " " + cond_lower
        # Directly include the condition name as a symptom term for disease_retrieval
        mapped = _SKIN_TERM_MAP.get(cond_lower)
        if mapped:
            symptoms.add(mapped)
        else:
            # Include clean condition name directly
            clean = cond.strip().lower()
            if len(clean) > 2:
                symptoms.add(clean)

    # From lesion_morphology
    morph = str(vision.get("lesion_morphology", "") or "").lower()
    combined_text += " " + morph

    # From distribution
    dist = str(vision.get("distribution", "") or "").lower()
    combined_text += " " + dist

    # From explanation
    explanation = str(vision.get("explanation", "") or "").lower()
    combined_text += " " + explanation

    # Map known terms
    for term, mapped in _SKIN_TERM_MAP.items():
        if term in combined_text:
            symptoms.add(mapped)

    # Also extract the body region as context
    body_region = str(vision.get("body_region", "") or "").lower()
    if body_region:
        symptoms.add(f"skin condition on {body_region}")

    return sorted(symptoms)[:10]   # cap at 10 to keep retrieval focused


def _extract_xray_symptoms(state: TriageState) -> list[str]:
    """
    Extracts symptom-like terms from xray_findings and vision metadata.
    """
    symptoms = set()

    # From xray_findings text (the LLaMA-generated explanation)
    xray_text = str(state.get("xray_findings", "") or "").lower()
    for term, mapped in _XRAY_TERM_MAP.items():
        if term in xray_text and mapped:
            symptoms.add(mapped)

    # From vision_findings if available (populated by medical_vision_node if running)
    vision = state.get("vision_findings") or {}
    for cond in vision.get("possible_conditions", []):
        cond_lower = str(cond).lower()
        mapped = _XRAY_TERM_MAP.get(cond_lower)
        if mapped:
            symptoms.add(mapped)
        elif len(cond_lower) > 2:
            symptoms.add(cond_lower)

    # Body region
    body_region = str(vision.get("body_region", "") or "").lower()
    if body_region and "xray" not in body_region:
        symptoms.add(f"pain in {body_region}")

    # Fallback: if xray_findings says fracture  unambiguously
    if not symptoms:
        symptoms.add("bone injury")
        symptoms.add("trauma")

    return sorted(symptoms)[:8]


def vision_symptom_bridge_node(state: TriageState) -> TriageState:
    """
    Converts vision analysis results into the symptom list expected by
    disease_retrieval, risk_evaluation and llm_brain.

    Sets state["symptoms"] and enriches state["user_input"] so the downstream
    nodes (disease_retrieval, llm_brain) receive the right context.

    Skips followup_check — images have already been analysed, no clarification needed.
    """
    intent = state.get("intent", "body_image")

    if intent == "xray":
        symptoms = _extract_xray_symptoms(state)
        xray_text = state.get("xray_findings", "")
        context = (
            f"Patient submitted an X-ray for analysis. "
            f"Findings: {xray_text[:400]}. "
            f"Extracted diagnostic terms: {', '.join(symptoms)}."
        )
        log_event(logger, "vision_bridge_xray",
                  symptom_count=len(symptoms), symptoms=symptoms)

    else:  # body_image
        vision = state.get("vision_findings", {}) or {}
        symptoms = _extract_skin_symptoms(vision)
        explanation = vision.get("explanation", "")
        conditions  = ", ".join(vision.get("possible_conditions", [])[:4])
        context = (
            f"Patient submitted a body/skin image for analysis. "
            f"Visual findings: {explanation[:300]}. "
            f"Possible conditions identified: {conditions}. "
            f"Extracted symptom terms: {', '.join(symptoms)}."
        )
        log_event(logger, "vision_bridge_body_image",
                  symptom_count=len(symptoms), symptoms=symptoms,
                  possible_conditions=vision.get("possible_conditions", []))

    # Populate symptoms so disease_retrieval can look them up
    state["symptoms"] = symptoms

    # Set user_input so llm_brain has full context
    state["user_input"] = context

    # Clear followup state — images skip clarification
    state["pending_followup"]         = ""
    state["followup_count"]           = 0
    state["symptom_extraction_failed"] = False
    state["next_action"]              = ""

    return state
