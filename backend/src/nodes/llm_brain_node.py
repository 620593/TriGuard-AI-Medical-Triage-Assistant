"""
llm_brain_node.py  (Version 5.1 — V5.1 FOLLOW-UP CONTEXT PATCH)
---------------------------------
Composes the final user-facing triage response using Groq LLaMA.

V3 (preserved):
    - Multilingual output: responds in the user's detected language.
    - Includes nutrition advice in the response when available.
    - Structured logging with token tracking.
    - All V2 anti-hallucination rules preserved.

V5 (preserved):
    - vision_error fast-exit.
    - user_input safety guard with last-5-messages scan.
    - Language embedded in prompt (eliminates translation round-trip).

# 🔥 V5.1 FOLLOW-UP CONTEXT PATCH:
    PATCH 1: After any successful response, stores:
                state["last_structured_summary"]
                state["last_risk_level"]
                state["last_intent"]
             so follow-up turns can reference the prior analysis.
    PATCH 3: Before building the standard LLaMA prompt, detects follow-up
             text turns (intent=medical_text + prior findings present) and
             constructs combined_input with prior findings + new question.
    PATCH 4: Replaces hard empty-input exit: if prior findings exist, re-
             explains them instead of returning an empty_input_response.
"""

from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from backend.src.fallback_responses import vision_error_response, empty_input_response  # 🔥 V5

import asyncio

logger = get_logger("llm_brain")


async def llm_brain_node(state: TriageState) -> TriageState:
    """
    Generates the final structured triage response using LLaMA.

    # 🔥 V5 DOCUMENT PIPELINE UPGRADE:
    - Checks vision_error flag: if True, returns structured safe fallback
      immediately without calling LLaMA (prevents hallucination on image failures).
    - Checks user_input: if empty, injects a safe fallback response.
      This ensures judge_validator never receives a blank response.
      (State safety rule: user_input must always be non-empty before this node.)

    Args:
        state: Contains all triage data.

    Returns:
        TriageState: Final response appended to messages.
    """
    next_action        = state.get("next_action", "")
    mental_health_flag = state.get("mental_health_flag", False)
    risk_level         = state.get("risk_level", "unknown")
    risk_score         = state.get("risk_score", 0.0)
    symptoms           = state.get("symptoms", [])
    retrieved_info     = state.get("retrieved_info", [])
    language           = state.get("language", "en")

    # ── 🔥 V5 DOCUMENT PIPELINE UPGRADE: Vision error fast-exit ─────────────────────
    # If vision API failed, return a structured safe message without calling LLaMA.
    # String sourced from fallback_responses (presentation layer) not inlined here.
    if state.get("vision_error"):
        state["messages"].append({"role": "assistant", "content": vision_error_response()})
        log_event(logger, "llm_brain_vision_error_exit",
                  reason="vision_error_flag", risk_level=risk_level)
        return state

    # ── 🔥 V5.1 FOLLOW-UP CONTEXT PATCH (PATCH 4 — context-aware empty guard) ─────
    # Replaces the old hard-exit when user_input is empty.
    # Priority order:
    #   1. user_input is present → use it directly (normal path)
    #   2. user_input empty but recent messages exist → recover from messages
    #   3. user_input empty but last_structured_summary exists → re-explain findings
    #   4. nothing available → structured empty_input_response (last resort)
    user_input = state.get("user_input", "").strip()
    last_summary = state.get("last_structured_summary", "")

    if not user_input:
        # Attempt 1: recover from recent message history (capped at 5, O(1))
        recent_messages = state.get("messages", [])[-5:]
        user_messages_text = [m["content"] for m in recent_messages if m.get("role") == "user"]
        if user_messages_text:
            user_input = user_messages_text[-1]
        elif last_summary:
            # 🔥 V5.1 PATCH 4: prior findings exist — re-explain instead of hard exit
            user_input = f"Please explain my previous results: {last_summary[:300]}"
            log_event(logger, "llm_brain_context_recovery",
                      reason="empty_input_prior_summary_reuse")
        else:
            # Truly nothing: structured fallback (last resort)
            state["messages"].append(
                {"role": "assistant", "content": empty_input_response(risk_level)}
            )
            log_event(logger, "llm_brain_empty_input_exit",
                      reason="no_user_input_no_summary")
            return state

    # ── Case 1: Follow-up question already added by followup_node ──────────────
    if next_action == "ask_followup":
        return state

    # ── Case 2: Mental health or critical emergency ────────────────────────────
    if next_action == "priority_interrupt":
        if mental_health_flag:
            alert = (
                "🚨 I hear you, and I want you to know support is available.\n\n"
                "Please reach out to a crisis helpline right now:\n"
                "  🇺🇸 National Suicide Prevention Lifeline: 988\n"
                "  🌐 International: https://www.befrienders.org\n\n"
                "If you are in immediate danger, please call emergency services (911/999/112).\n"
                "You are not alone. Help is one call away."
            )
        else:
            symptom_str = ", ".join(symptoms) if symptoms else "the symptoms described"
            alert = (
                f"🚨 URGENT MEDICAL ALERT\n\n"
                f"Based on your reported symptoms ({symptom_str}), this appears to be "
                f"a potentially life-threatening situation (Risk: {risk_level.upper()}).\n\n"
                "⚡ Call emergency services (911 / 999 / 112) IMMEDIATELY "
                "or go to the nearest emergency room.\n\n"
                "Do not wait. This triage tool does NOT replace emergency medical care."
            )

        # Translate emergency alert if non-English
        if language != "en":
            translated = await _translate_response(alert, language)
            if translated:
                alert = translated

        state["messages"].append({"role": "assistant", "content": alert})
        log_event(logger, "emergency_alert", risk_level=risk_level,
                  mental_health=mental_health_flag)
        return state

    # ── Case 3: X-ray already handled upstream ──────────────────────────────────
    # xray_analysis_node appends the full assistant message to state["messages"]
    # and stores the explanation in state["xray_findings"]. If that field exists,
    # there is nothing for llm_brain to add — return immediately to avoid a
    # second generic response that would overwrite the X-ray explanation.
    if state.get("xray_findings"):
        # 🔥 V5.1 PATCH 1: store xray findings for follow-up context bridging
        xray_summary = state.get("xray_findings", "")
        state["last_structured_summary"] = str(xray_summary)[:600]
        state["last_risk_level"]         = risk_level
        state["last_intent"]             = "xray"
        log_event(logger, "xray_passthrough", reason="xray_findings_already_set")
        return state

    # ── Case 4: Medical Vision Explanation ──────────────────────────────────────
    # Guard: only use vision explanation for actual body images.
    # If intent was redirected to 'medical_report' by medical_vision_node
    # (V4.1 doc redirect), we skip this branch even if vision_findings exist.
    # The OCR pipeline has already injected text; use the standard text path.
    vision_findings = state.get("vision_findings")
    intent = state.get("intent", "")
    if vision_findings and intent != "medical_report":
        image_type = vision_findings.get("image_type", "unknown")
        findings_list = ", ".join(vision_findings.get("visual_findings", []))
        confidence = vision_findings.get("confidence", 0.0)

        if confidence < 0.6:
            response = (
                f"🩺 Vision Analysis ({image_type.upper()}):\n\n"
                "I detected some visual patterns, but the image quality or clarity "
                "is insufficient for a confident assessment.\n\n"
                "💡 Please upload a clearer, well-lit image for a better analysis.\n"
                "⚠️ This could indicate various conditions, and a clearer view is needed."
            )
        else:
            # P3.1 Fix: Use pre-generated explanation from vision tool if available
            response = vision_findings.get("explanation")

            if not response:
                prompt = (
                    "You are TriGuard AI. Analyze these visual medical findings.\n"
                    f"Image Type: {image_type}\n"
                    f"Findings: {findings_list}\n\n"
                    "Rules:\n"
                    "- Use triage-safe language.\n"
                    "- NEVER confirm a diagnosis.\n"
                    "- Use phrases like: 'This may be consistent with...', 'This could indicate...'.\n"
                    "- Keep it under 6 lines.\n\n"
                    "Response:"
                )
                response = await asyncio.to_thread(call_llama, prompt, max_tokens=300)

        # Add mandatory disclaimer if it doesn't exist
        if "Disclaimer" not in response and "disclaimer" not in response.lower():
            response += (
                "\n\n⚠️ Disclaimer: This is an automated visual analysis. "
                "It does NOT replace a clinical examination by a doctor."
            )

        # Translate if non-English
        if language != "en":
            translated = await _translate_response(response, language)
            if translated:
                response = translated

        state["messages"].append({"role": "assistant", "content": response})
        # 🔥 V5.1 PATCH 1: store vision explanation for follow-up context bridging
        state["last_structured_summary"] = response[:600]
        state["last_risk_level"]         = risk_level
        state["last_intent"]             = "body_image"
        log_event(logger, "vision_explained", type=image_type, confidence=confidence)
        return state

    # ── Case 5: Standard LLaMA brain response ──────────────────────────────────
    symptom_str = ", ".join(symptoms) if symptoms else "symptoms described"
    context_lines = retrieved_info[:3]
    context_snippet = " | ".join(context_lines)[:600] if context_lines else "No medical context retrieved."

    # 🔥 V5.1 FOLLOW-UP CONTEXT PATCH (PATCH 3): build combined_input for follow-up turns.
    # Detects: intent=medical_text (text turn) AND prior image/xray findings exist.
    # Injects last_structured_summary + last_risk_level into the prompt input so
    # LLaMA has the clinical context it needs to answer "why am I getting leg pain?"
    last_summary  = state.get("last_structured_summary", "")
    last_risk     = state.get("last_risk_level", "")
    intent        = state.get("intent", "")
    is_followup   = (intent == "medical_text" and bool(last_summary))

    if is_followup:
        combined_input = (
            f"Previous medical findings:\n{last_summary}\n"
            f"Risk level from prior analysis: {last_risk.upper() if last_risk else 'UNKNOWN'}\n\n"
            f"User follow-up question:\n{user_input}"
        )
        log_event(logger, "llm_brain_followup_context",
                  prior_intent=state.get("last_intent", ""),
                  prior_risk=last_risk)
    else:
        combined_input = user_input

    # 🔥 V5 DOCUMENT PIPELINE UPGRADE (P4.1 fix): embed language instruction in prompt
    # instead of a sequential post-translation API call, which saves one full LLaMA
    # round-trip for every non-English request.
    lang_instruction = (
        f"IMPORTANT: Write your entire response in the '{language}' language. "
        "Do NOT translate labels (SUMMARY, RISK_LEVEL, etc.) — keep them in English.\n"
        if language != "en"
        else ""
    )

    # Use strictly labelled sections so output_parser can reliably extract them.
    # Do NOT add extra free-text — the parser relies on exact section headers.
    # 🔥 V5.1 PATCH 3: combined_input replaces plain symptom_str when follow-up detected.
    prompt = (
        "You are TriGuard AI, a conservative medical triage assistant.\n"
        f"{lang_instruction}"
        "RULES:\n"
        "- NEVER diagnose, prescribe, or invent disease names.\n"
        "- ONLY use the symptoms + context provided. Do not add others.\n"
        "- Be empathetic, clear, and concise.\n\n"
        "Output EXACTLY in this format (do not change the labels):\n"
        "SUMMARY: [1-2 sentence plain-English summary of the patient's concern]\n"
        f"RISK_LEVEL: {risk_level.upper()}\n"
        f"RISK_SCORE: {risk_score:.1f}/10\n"
        "ACTION: [clear, actionable step the patient should take RIGHT NOW]\n"
        "RED_FLAGS: [2-3 specific warning signs that require immediate emergency care]\n\n"
        f"Patient input: {combined_input[:800]}\n"
        f"Medical context (from search): {context_snippet}\n\n"
        "Write the triage response now:"
    )

    response = await asyncio.to_thread(call_llama, prompt, max_tokens=350)

    if not response:
        response = (
            f"SUMMARY: You reported {symptom_str}. A triage assessment has been completed.\n"
            f"RISK_LEVEL: {risk_level.upper()}\n"
            f"RISK_SCORE: {risk_score:.1f}/10\n"
            "ACTION: Please consult a healthcare professional for a full assessment.\n"
            "RED_FLAGS: Worsening symptoms, difficulty breathing, chest pain, or confusion."
        )

    # Append nutrition advice as a labelled section (output_parser will extract it)
    nutrition = state.get("nutrition_advice", "")
    if nutrition:
        response += f"\nDIETARY: {nutrition}"

    # Append mandatory disclaimer as a labelled section
    response += (
        "\nDISCLAIMER: This is a triage tool only, NOT a medical diagnosis. "
        "Always consult a licensed physician for personal medical advice."
    )

    # 🔥 V5 DOCUMENT PIPELINE UPGRADE (P4.1): No post-translation call needed here.
    # Language is injected directly into the prompt above (lang_instruction).
    # _translate_response is kept only for emergency/vision fixed-template paths.

    state["messages"].append({"role": "assistant", "content": response})

    # 🔥 V5.1 FOLLOW-UP CONTEXT PATCH (PATCH 1):
    # Store structured output for cross-turn context bridging.
    # Future follow-up text turns will use these fields to build combined_input.
    state["last_structured_summary"] = response[:600]   # cap to avoid state bloat
    state["last_risk_level"]         = risk_level
    state["last_intent"]             = state.get("intent", "medical_text")

    log_event(logger, "response_generated",
              risk_level=risk_level,
              language=language,
              response_length=len(response))

    return state


async def _translate_response(text: str, target_lang: str) -> str:
    """
    Translates a response to the target language using LLaMA.

    Returns:
        str: Translated text, or empty string on failure.
    """
    prompt = (
        f"Translate this medical triage response to {target_lang} language. "
        "Keep all emojis, formatting, and medical terms intact. "
        "Return ONLY the translation.\n\n"
        f"Text:\n{text}\n\nTranslation:"
    )
    res = await asyncio.to_thread(call_llama, prompt, max_tokens=500)
    return res.strip()
