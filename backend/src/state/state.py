"""
state.py  (Version 3)
---------------------
Central state object passed through every LangGraph node.

V3 additions:
    session_id       : MongoDB session identifier.
    user_id          : User identifier for multi-user support.
    language         : Detected/requested language code (e.g. 'en', 'hi', 'es').
    original_input   : Raw user input before translation (for response translation).
    input_mode       : 'text' | 'voice' | 'image' | 'xray'.
    ocr_text         : Extracted text from uploaded images (prescriptions, lab reports).
    xray_findings    : Structured findings from X-ray analysis model.
    nutrition_advice  : Dietary suggestions for low/moderate risk cases.
    nutrition_image   : Base64 or URL of generated meal image.
    judge_passed     : Whether the judge-validator LLM approved the response.
    judge_feedback   : Reason if judge rejected the response.
    audio_url        : URL/path to TTS audio output.
"""

from typing import TypedDict, List, Optional


class TriageState(TypedDict):
    """
    Central state for the V3 medical triage pipeline.
    All nodes read/write to this shared state object.
    """

    # ── Core fields (from V2) ──────────────────────────────────────────────────
    messages:           List[dict]   # Conversation history [{role, content}]
    symptoms:           List[str]    # LLaMA-extracted symptom keywords
    followup_count:     int          # Follow-up questions used (0-3)
    retrieved_info:     List[str]    # Tavily medical summaries (max 3)
    risk_score:         float        # 0.0 – 10.0
    risk_level:         str          # 'low' | 'moderate' | 'high' | 'critical'
    risk_confidence:    float        # 0.0 – 1.0
    mental_health_flag: bool         # True = crisis detected
    next_action:        str          # '' | 'ask_followup' | 'priority_interrupt'
    _mid_session:       bool         # True = conversation loop re-entry

    # ── V3: Session & User ─────────────────────────────────────────────────────
    session_id:         str          # MongoDB ObjectId string
    user_id:            str          # User identifier

    # ── V3: Multilingual ───────────────────────────────────────────────────────
    language:           str          # ISO 639-1 code: 'en', 'hi', 'es', etc.
    original_input:     str          # Raw user input (pre-translation)

    # ── V3: Input mode ─────────────────────────────────────────────────────────
    input_mode:         str          # 'text' | 'voice' | 'image' | 'xray'

    # ── V3: OCR pipeline ──────────────────────────────────────────────────────
    ocr_text:           str          # Extracted text from image uploads

    # ── V3: X-ray pipeline ─────────────────────────────────────────────────────
    xray_findings:      str          # Structured findings from vision model

    # ── V3: Nutrition ──────────────────────────────────────────────────────────
    nutrition_advice:   str          # Dietary suggestions text
    nutrition_image:    str          # Base64 or URL of generated meal image

    # ── V3: Judge validator ────────────────────────────────────────────────────
    judge_passed:       bool         # True if judge approved the response
    judge_feedback:     str          # Rejection reason (if any)

    # ── V3: Voice output ───────────────────────────────────────────────────────
    audio_url:          str          # Path/URL to TTS audio output
