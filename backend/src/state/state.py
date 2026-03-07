"""
state.py  (Version 6 — V6 Final Architecture)
----------------------------------------------
Central state contract for TriGuard AI V6.

V6 design rules:
    - All fields are Optional (total=False) — nodes only touch keys they own.
    - tools/ NEVER write to state.
    - nodes/ are the ONLY modules that mutate state.
    - New fields: reasoning_input, red_flag_triggered, urgency, llm_output,
      formatted_response, voice_response_required, audio_path,
      emergency_call_triggered, call_sid, system_trace, fallback_used,
      prior_history_context, medication_requested, google_oauth.
"""

from typing import TypedDict, List, Optional, Any


class TriageState(TypedDict, total=False):
    """
    Shared state for the V6 triage pipeline.

    TypedDict with total=False so every field is optional at creation time —
    individual nodes only need to set the keys they touch.
    """

    # ── Core conversation ─────────────────────────────────────────────────────
    messages:                List[dict]   # [{role, content}, ...] conversation history
    original_input:          str          # Raw user message (before pre-processing)

    # ── Intent classification ─────────────────────────────────────────────────
    intent:                  str          # 'medical_text' | 'medical_report' | 'xray' | 'body_image' | 'casual'
    image_type_hint:         str          # Frontend hint: 'report' | 'prescription' | etc.
    user_input:              str          # Normalised text input for the current turn

    # ── Symptom pipeline ──────────────────────────────────────────────────────
    symptoms:                List[str]    # Extracted symptom phrases
    retrieved_info:          List[str]    # Snippets from Tavily medical search
    disease_candidates:      List[str]    # Disease names from vector store retrieval

    # ── Risk assessment ───────────────────────────────────────────────────────
    risk_level:              str          # 'low' | 'moderate' | 'high' | 'critical' | 'not_applicable' | 'unknown'
    risk_score:              float        # 0–10 numeric score
    risk_confidence:         float        # 0–1 confidence in the risk assessment

    # ── 🔥 V6: Red flag engine ────────────────────────────────────────────────
    red_flag_triggered:      bool         # True when config-driven red flag rule matched
    urgency:                 str          # 'routine' | 'urgent' | 'emergency' | 'critical'

    # ── 🔥 V6: Context synthesizer output ────────────────────────────────────
    reasoning_input:         str          # Merged context (prior findings + current query) for llm_brain

    # ── 🔥 V6: Structured LLM output ─────────────────────────────────────────
    llm_output:              dict         # Strict JSON from llm_brain_node:
                                          # {clinical_summary, possible_causes, risk_level,
                                          #  recommended_action, urgency, confidence_score}

    # ── 🔥 V6: Response layer ─────────────────────────────────────────────────
    formatted_response:      str          # Tone-applied, presentation-ready text from response_node
    final_response:          str          # Final output delivered to the user

    # ── 🔥 V6: Voice I/O ─────────────────────────────────────────────────────
    voice_response_required: bool         # Set by speech_to_text_node; triggers text_to_speech_node
    audio_path:              str          # File path to generated TTS audio

    # ── 🔥 V6: Emergency escalation ──────────────────────────────────────────
    emergency_call_triggered: bool        # True after a successful Twilio call
    call_sid:                str          # Twilio call SID for deduplication
    user_consent_for_call:   bool         # User must have explicitly consented

    # ── 🔥 V6: Observability trace ────────────────────────────────────────────
    system_trace:            dict         # Completed at end of pipeline — single trace dict per turn
    fallback_used:           bool         # True if any fallback response was delivered

    # ── Session & User ────────────────────────────────────────────────────────
    session_id:              str
    user_id:                 str
    language:                str          # ISO 639-1: 'en', 'hi', 'es', etc.
    timestamp:               str          # ISO 8601 (set by save_session)

    # ── Vision (in-memory only) ───────────────────────────────────────────────
    image_input:             Any          # Raw bytes or base64; discarded after processing
    input_mode:              str          # 'text' | 'voice' | 'image' | 'xray'
    vision_findings:         dict         # {image_type, visual_findings, confidence, explanation}

    # ── OCR & X-ray ───────────────────────────────────────────────────────────
    ocr_text:                str          # Extracted text from medical report images
    extracted_text:          str          # Canonical OCR output used by text pipeline downstream
    xray_findings:           str          # Structured X-ray analysis output

    # ── V5 document pipeline flags (preserved) ────────────────────────────────
    is_document:             bool         # True when vision classified image as document
    vision_error:            bool         # True when vision API call failed
    ocr_completed:           bool         # True once OCR finished

    # ── Cross-turn context bridging (V5.1 preserved) ─────────────────────────
    last_structured_summary: str          # Last triage/vision summary (capped 600 chars)
    last_risk_level:         str          # Risk level from last completed analysis
    last_intent:             str          # Intent of last completed analysis

    # ── Pipeline control ──────────────────────────────────────────────────────
    next_action:             str          # '' | 'ask_followup' | 'priority_interrupt'
    judge_passed:            bool         # Whether judge_validator approved the response
    judge_feedback:          str          # Reason if judge flagged a problem
    regeneration_count:      int          # Number of judge-triggered regenerations (max 2)
    force_accepted:          bool         # True when judge exhausted retries
    trigger_nutrition_node:  bool         # Flag to trigger nutrition analysis

    # ── Mental health ─────────────────────────────────────────────────────────
    mental_health_flag:      bool         # True if crisis language detected

    # ── V6 Features ───────────────────────────────────────────────────────────
    prior_history_context:   str          # (cross-session retrieved history)
    medication_requested:    bool         # (user asked for medication)
    google_oauth:            bool         # (user signed in via Google)

    # ── Nutrition ─────────────────────────────────────────────────────────────
    nutrition_advice:           str          # Text dietary suggestions
    nutrition_image:            str          # URL to generated meal image (optional, legacy)
    nutrition_output:           dict         # JSON output from nutrition_node
    nutrition_image_required:   bool         # Set by nutrition_node; triggers async_nutrition_image_node
    nutrition_image_url:        str          # URL/path populated by async_nutrition_image_node after response

    # ── Internal control (not persisted) ──────────────────────────────────────
    use_history:             bool         # True only when user explicitly requests past history
    followup_count:          int          # How many follow-up questions have been asked
    new_session:             bool         # True on the FIRST turn of a new session (no prior history to load)

    # ── In-session memory (V8) ────────────────────────────────────────────────
    session_memory:          str          # Assembled SESSION MEMORY block (last 10 turns) for context_synthesizer
    last_symptoms:           List[str]    # Accumulated symptom list from prior turns in this session
