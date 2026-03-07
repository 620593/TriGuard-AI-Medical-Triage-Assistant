"""
medical_vision_node.py  (Version 5 — V5 DOCUMENT PIPELINE UPGRADE)
--------------------------------------------------
LangGraph node for in-memory medical vision pipeline.
Orchestrates vision classification without cloud storage.
Safety: Validates image size, format, and error state.
Performance: Asynchronous execution with timeout guard.

# 🔥 V5 DOCUMENT PIPELINE UPGRADE changes:
    1. Catches model_decommissioned, API 400, and timeout errors explicitly.
       On any vision failure:
           state["risk_level"]      = "unknown"
           state["risk_confidence"] = 0.0    # uses TypedDict field, not ad-hoc 'confidence'
           state["vision_error"]    = True
    2. Document images (image_type in DOCUMENT_IMAGE_TYPES):
           state["is_document"] = True
           state["intent"]      = "medical_report"
           state["risk_level"]  = "not_applicable"
       These drive _route_after_vision → ocr_scan deterministically.
    3. Structured document findings with full V5 metadata preserved.
    4. Existing body/skin paths unchanged.

V4.1 (preserved):
    - Document detection: if vision identifies a document/report/prescription,
      re-routes to 'medical_report' intent and preserves image_input for OCR.
"""

from typing import Dict, Any
from backend.src.state.state import TriageState
from backend.src.tools.vision_classifier_tool import analyze_medical_image
from backend.src.logging.logger import get_logger, log_event
from backend.src.pipeline_config import DOCUMENT_IMAGE_TYPES

logger = get_logger("medical_vision")

# Max image size: 10MB
MAX_IMAGE_SIZE = 10 * 1024 * 1024


# 🔥 UPGRADE V5: Structured safe fallback builders

def _make_fail_findings(reason: str) -> Dict[str, Any]:
    """
    Returns a safe vision_findings structure when the model fails.
    confidence=0.0, risk_level="unknown" — signals risk_evaluation to skip.
    """
    return {
        "image_type": "unknown",
        "visual_findings": [],
        "confidence": 0.0,
        "risk_level": "unknown",   # 🔥 UPGRADE V5
        "explanation": (
            f"⚠️ Image analysis could not be completed: {reason} "
            "Please upload a clearer JPG or PNG and try again. "
            "This is an automated system — consult a doctor for medical advice."
        ),
    }


def _make_document_findings(vision_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    # 🔥 UPGRADE V5: Structured document findings.
    Preserves all V5 document metadata from vision_classifier_tool.
    Sets risk_level="not_applicable" for document images (no medical risk scoring).
    """
    return {
        "image_type":               "document",
        "document_type":            vision_results.get("document_type", "other"),
        "org_name":                 vision_results.get("org_name", "not_visible"),
        "is_handwritten":           vision_results.get("is_handwritten", False),
        "medications_listed":       vision_results.get("medications_listed", False),
        "patient_details_visible":  vision_results.get("patient_details_visible", False),
        "visual_findings":          vision_results.get("visual_findings", []),
        "confidence":               vision_results.get("confidence", 0.0),
        "risk_level":               "not_applicable",  # 🔥 UPGRADE V5
        "explanation":              vision_results.get("explanation", ""),
    }


async def medical_vision_node(state: TriageState) -> TriageState:
    """
    Processes image bytes/base64 from state['image_input'] and extracts findings.

    # 🔥 UPGRADE V5:
    - vision model failure → risk_level="unknown" in vision_findings
    - document image      → risk_level="not_applicable" + redirect to OCR
    - All error paths     → structured fallback, no bare exception propagation

    V4.1 (preserved):
    - If vision identifies a document, updates `intent` to 'medical_report'
      and PRESERVES `image_input` so the graph routing edge redirects to ocr_scan.
    """
    image_data = state.get("image_input")

    if not image_data:
        log_event(logger, "vision_node_skipped", reason="no_image_data")
        return state

    # ── Guard: Size check ──────────────────────────────────────────────────────
    if isinstance(image_data, bytes) and len(image_data) > MAX_IMAGE_SIZE:
        log_event(logger, "vision_node_failed", reason="image_too_large")
        state["vision_findings"] = _make_fail_findings(
            "The image is too large (max 10MB). Please upload a smaller file."
        )
        # 🔥 V5 DOCUMENT PIPELINE UPGRADE: explicit error state flags
        state["risk_level"]      = "unknown"
        state["risk_confidence"] = 0.0   # TypedDict field (was incorrectly 'confidence')
        state["vision_error"]    = True
        state["image_input"] = None
        return state

    # ── Vision Classification ──────────────────────────────────────────────────
    # 🔥 UPGRADE V5: All error handling is inside analyze_medical_image.
    # The tool catches model_decommissioned, API 400, timeout, and JSON parse errors.
    # It always returns a structured dict — never raises here.
    vision_results = await analyze_medical_image(image_data)

    image_type = vision_results.get("image_type", "unknown").lower()
    confidence  = vision_results.get("confidence", 0.0)

    # ── 🔥 V5 DOCUMENT PIPELINE UPGRADE: Vision model failure path ──────────────
    # confidence == 0.0 and image_type == "unknown" = model could not analyze image
    if confidence == 0.0 and image_type == "unknown":
        fallback_findings = _make_fail_findings(
            vision_results.get("explanation", "Model returned zero confidence.")
        )
        state["vision_findings"] = fallback_findings
        state["risk_level"]      = "unknown"
        state["risk_confidence"] = 0.0   # TypedDict field (was incorrectly 'confidence')
        state["vision_error"]    = True             # 🔥 V5 DOCUMENT PIPELINE UPGRADE
        state["image_input"]  = None
        log_event(logger, "vision_model_failed",
                  reason="zero_confidence", explanation=vision_results.get("explanation", ""))
        return state

    # ── 🔥 V5 DOCUMENT PIPELINE UPGRADE: Document image path ──────────────────
    # Document images route to OCR → medical text pipeline.
    # is_document=True drives _route_after_vision → ocr_scan deterministically.
    # risk_level="not_applicable" prevents risk_evaluation from scoring a document.
    if image_type in DOCUMENT_IMAGE_TYPES:
        state["vision_findings"] = _make_document_findings(vision_results)
        state["risk_level"]      = "not_applicable"   # 🔥 V5 DOCUMENT PIPELINE UPGRADE
        state["intent"]          = "medical_report"    # drives routing edge → ocr_scan
        state["is_document"]     = True                # 🔥 V5 DOCUMENT PIPELINE UPGRADE
        # Do NOT clear image_input — ocr_scan_node needs it downstream
        log_event(logger, "vision_document_redirect",
                  detected_type=image_type,
                  document_type=vision_results.get("document_type", "other"),
                  new_intent="medical_report",
                  is_document=True,
                  risk_level="not_applicable")
        return state

    # ── Standard body/skin/xray image path ────────────────────────────────────
    findings = {
        "image_type":         image_type,
        "visual_findings":    vision_results.get("visual_findings", []),
        "lesion_morphology":  vision_results.get("lesion_morphology"),
        "color_description":  vision_results.get("color_description"),
        "distribution":       vision_results.get("distribution"),
        "severity":           vision_results.get("severity"),
        "possible_conditions": vision_results.get("possible_conditions", []),
        "confidence":         confidence,
        "explanation":        vision_results.get("explanation", ""),
    }

    state["vision_findings"] = findings
    state["image_input"]     = None   # discard heavy binary data immediately

    log_event(logger, "vision_analysis_completed",
              type=image_type,
              confidence=confidence)

    return state
