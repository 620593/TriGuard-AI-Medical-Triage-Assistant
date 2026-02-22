"""
llm_brain_node.py  (Version 3)
---------------------------------
Composes the final user-facing triage response using Groq LLaMA.

V3 changes:
    - Multilingual output: responds in the user's detected language.
    - Includes nutrition advice in the response when available.
    - Structured logging with token tracking.
    - All V2 anti-hallucination rules preserved.
"""

from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("llm_brain")


def llm_brain_node(state: TriageState) -> TriageState:
    """
    Generates the final structured triage response using LLaMA.

    Args:
        state: Contains all triage data.

    Returns:
        TriageState: Final response appended to messages.
    """
    next_action = state.get("next_action", "")
    mental_health_flag = state.get("mental_health_flag", False)
    risk_level = state.get("risk_level", "unknown")
    risk_score = state.get("risk_score", 0.0)
    symptoms = state.get("symptoms", [])
    retrieved_info = state.get("retrieved_info", [])
    language = state.get("language", "en")

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
            translated = _translate_response(alert, language)
            if translated:
                alert = translated

        state["messages"].append({"role": "assistant", "content": alert})
        log_event(logger, "emergency_alert", risk_level=risk_level,
                  mental_health=mental_health_flag)
        return state

    # ── Case 3: Standard LLaMA brain response ─────────────────────────────────
    symptom_str = ", ".join(symptoms) if symptoms else "symptoms described"
    context_lines = retrieved_info[:3]
    context_snippet = " | ".join(context_lines)[:600] if context_lines else "No medical context retrieved."

    prompt = (
        "You are TriGuard AI, a medical triage assistant. "
        "You MUST NOT diagnose, prescribe, or invent disease names.\n"
        "You MUST only use the medical context provided below.\n"
        "Keep your response to 8 lines or fewer.\n\n"
        "Use EXACTLY this format:\n"
        "🩺 Summary: [1-2 line summary of patient concern]\n"
        f"📊 Risk Level: {risk_level.upper()} ({risk_score:.1f}/10)\n"
        "💡 Suggested Action: [what to do next]\n"
        "⚠️ When To Seek Immediate Help: [red flag signs to watch for]\n\n"
        f"Patient symptoms: {symptom_str}\n"
        f"Medical context (from search): {context_snippet}\n\n"
        "Now write the triage response:"
    )

    response = call_llama(prompt, max_tokens=350)

    if not response:
        response = (
            f"🩺 Summary: You reported: {symptom_str}.\n"
            f"📊 Risk Level: {risk_level.upper()} ({risk_score:.1f}/10)\n"
            "💡 Suggested Action: Please consult a healthcare professional for assessment.\n"
            "⚠️ When To Seek Immediate Help: Worsening symptoms, difficulty breathing, or chest pain."
        )

    # Append nutrition advice if available
    nutrition = state.get("nutrition_advice", "")
    if nutrition:
        response += f"\n\n🥗 Nutrition Suggestions:\n{nutrition}"

    # Mandatory disclaimer
    response += (
        "\n\n⚠️ Disclaimer: This is a triage tool only, NOT a medical diagnosis. "
        "Always consult a licensed physician."
    )

    # Translate if non-English
    if language != "en":
        translated = _translate_response(response, language)
        if translated:
            response = translated

    state["messages"].append({"role": "assistant", "content": response})

    log_event(logger, "response_generated",
              risk_level=risk_level,
              language=language,
              response_length=len(response))

    return state


def _translate_response(text: str, target_lang: str) -> str:
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
    return call_llama(prompt, max_tokens=500).strip()
