"""
state.py  (Version 5 — V5 Document Pipeline)
-----------------------------------------
Central state object for TriGuard AI V5.
All fields used by any node/tool in the pipeline are declared here.

V4 additions (preserved):
    - intent: Classification routing key
    - disease_candidates: Vector store retrieval results
    - svm_confidence: Rule-based confidence calibration
    - ocr_text: OCR-extracted text from medical reports
    - xray_findings: Structured X-ray analysis output
    - validated_response: Judge-approved response content
    - needs_nutrition_image: Flag for nutrition image generation
    - final_response: Formatted response ready for delivery
    - regeneration_count: Judge retry counter
    - image_type_hint: Frontend hint for image classification
    - _mid_session: Internal flag for follow-up loop re-entry

# 🔥 V5 DOCUMENT PIPELINE UPGRADE additions:
    - is_document: True when vision classified image as a document
    - vision_error: True when vision API failed (timeout/400/decommissioned)
    - extracted_text: Canonical OCR output used by downstream text pipeline
    - user_input: Normalised text input surfaced to llm_brain for response generation
    - ocr_completed: True when OCR finished and text injected into messages
"""

from typing import TypedDict, List, Optional, Any


class TriageState(TypedDict, total=False):
    """
    Shared state for the V4 triage pipeline.

    TypedDict with total=False so every field is optional at creation time —
    individual nodes only need to set the keys they touch.
    """

    # ── Core conversation ────────────────────────────────────────────────────
    messages:              List[dict]   # [{role, content}, ...] full history
    original_input:        str          # Raw user message (before translation)

    # ── Intent classification ────────────────────────────────────────────────
    intent:                str          # 'medical_text' | 'medical_report' | 'xray' | 'body_image' | 'casual'
    image_type_hint:       str          # Frontend hint: 'report' | 'prescription' | etc.

    # ── Symptom pipeline ────────────────────────────────────────────────────
    symptoms:              List[str]    # Extracted symptom phrases (English)
    followup_count:        int          # How many follow-up questions have been asked
    retrieved_info:        List[str]    # Snippets from Tavily medical search
    disease_candidates:    List[str]    # Disease names from vector store retrieval

    # ── Risk assessment ──────────────────────────────────────────────────────
    risk_level:            str          # 'low' | 'moderate' | 'high' | 'critical'
    risk_score:            float        # 0–10 numeric score
    risk_confidence:       float        # 0–1 confidence in the risk assessment
    svm_confidence:        float        # 0–1 SVM-calibrated confidence

    # ── Session & User ───────────────────────────────────────────────────────
    session_id:            str
    user_id:               str
    language:              str          # ISO 639-1 code: 'en', 'hi', 'es', etc.
    timestamp:             str          # ISO 8601 timestamp (set by save_session)

    # ── Vision (in-memory only — cleared after processing) ──────────────────
    image_input:           Any          # Raw bytes or base64 string; discarded after use
    input_mode:            str          # 'text' | 'voice' | 'image' | 'xray'
    vision_findings:       dict         # {image_type, visual_findings, confidence, explanation}

    # ── OCR & X-ray ─────────────────────────────────────────────────────────
    ocr_text:              str          # Extracted text from medical report images
    xray_findings:         str          # Structured X-ray analysis output

    # ── Mental health ────────────────────────────────────────────────────────
    mental_health_flag:    bool         # True if crisis language detected

    # ── Pipeline control ─────────────────────────────────────────────────────
    next_action:           str          # '' | 'ask_followup' | 'priority_interrupt'
    judge_passed:          bool         # Whether judge_validator approved the response
    judge_feedback:        str          # Reason if judge flagged a problem
    regeneration_count:    int          # Number of judge-triggered regenerations (max 2)
    force_accepted:        bool         # True when judge exhausted retries but response accepted

    # ── Response layer ───────────────────────────────────────────────────────
    validated_response:    str          # Judge-approved response content
    needs_nutrition_image: bool         # Flag to trigger nutrition image generation
    final_response:        str          # Formatted final output for delivery

    # ── Nutrition ────────────────────────────────────────────────────────────
    nutrition_advice:      str          # Text dietary suggestions
    nutrition_image:       str          # URL to generated meal image (optional)

    # ── TTS output ───────────────────────────────────────────────────────────
    audio_url:             str          # Path/URL of generated TTS audio file

    # ── Internal control (not persisted) ─────────────────────────────────────
    _mid_session:          bool         # True during follow-up loop re-entry
    use_history:           bool         # True only when user explicitly requests past history

    # ── 🔥 V5 DOCUMENT PIPELINE UPGRADE ──────────────────────────────────────
    is_document:           bool         # True when vision classified image as document type
    vision_error:          bool         # True when vision API call failed (timeout/400/decommissioned)
    extracted_text:        str          # Canonical OCR output (used by text pipeline downstream)
    user_input:            str          # Normalised text input surfaced to llm_brain for response
    ocr_completed:         bool         # True once OCR finished and text injected into messages

    # ── 🔥 V5.1 FOLLOW-UP CONTEXT PATCH ──────────────────────────────────────
    last_structured_summary: str        # Last successful triage/vision summary (cross-turn context)
    last_risk_level:          str        # Risk level from last completed analysis (cross-turn context)
    last_intent:               str        # Intent of last completed analysis ('xray','body_image',etc.)
