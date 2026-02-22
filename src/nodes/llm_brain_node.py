"""
llm_brain_node.py  (NEW — Version 2)
--------------------------------------
Composes the final user-facing triage response using Groq LLaMA.

Replaces V1's template-based response_node with a LLaMA-generated response.

Rules (HARD — anti-hallucination):
  - LLaMA may only use retrieved_info as disease context. It must not invent conditions.
  - No diagnosis. No prescription. No disease names beyond what Tavily returned.
  - Response ≤ 8 lines, structured with the four emoji headers.
  - If mental_health_flag is True → include crisis helpline guidance.
  - If next_action == 'ask_followup' → return the follow-up question already in messages.
  - If next_action == 'priority_interrupt' → return emergency alert.

Input:
    state (TriageState): Fully populated state from all prior nodes.

Returns:
    TriageState: Final assistant message appended to state["messages"].
"""

from src.tools.groq_llama_tool import call_llama
from src.state.state import TriageState


def llm_brain_node(state: TriageState) -> TriageState:
    """
    Generates the final structured triage response using LLaMA.

    Args:
        state (TriageState): Contains all triage data.

    Returns:
        TriageState: Final response appended to messages.
    """
    next_action = state.get("next_action", "")
    mental_health_flag = state.get("mental_health_flag", False)
    risk_level = state.get("risk_level", "unknown")
    risk_score = state.get("risk_score", 0.0)
    symptoms = state.get("symptoms", [])
    retrieved_info = state.get("retrieved_info", [])

    # ── Case 1: Still waiting for user input → return current follow-up question ──
    if next_action == "ask_followup":
        # Follow-up question is already the last assistant message from followup_node
        return state

    # ── Case 2: Mental health or critical emergency ────────────────────────────
    if next_action == "priority_interrupt":
        if mental_health_flag:
            # Specific crisis guidance for mental health
            alert = (
                "🚨 I hear you, and I want you to know support is available.\n\n"
                "Please reach out to a crisis helpline right now:\n"
                "  🇺🇸 National Suicide Prevention Lifeline: 988\n"
                "  🌐 International: https://www.befrienders.org\n\n"
                "If you are in immediate danger, please call emergency services (911/999/112).\n"
                "You are not alone. Help is one call away."
            )
        else:
            # Medical emergency alert
            symptom_str = ", ".join(symptoms) if symptoms else "the symptoms described"
            alert = (
                f"🚨 URGENT MEDICAL ALERT\n\n"
                f"Based on your reported symptoms ({symptom_str}), this appears to be "
                f"a potentially life-threatening situation (Risk: {risk_level.upper()}).\n\n"
                "⚡ Call emergency services (911 / 999 / 112) IMMEDIATELY "
                "or go to the nearest emergency room.\n\n"
                "Do not wait. This triage tool does NOT replace emergency medical care."
            )
        state["messages"].append({"role": "assistant", "content": alert})
        return state

    # ── Case 3: Standard LLaMA brain response ─────────────────────────────────
    symptom_str = ", ".join(symptoms) if symptoms else "symptoms described"

    # Only pass summarised Tavily context to LLaMA (cap at 600 chars to be concise)
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

    # Fallback if LLaMA returns nothing
    if not response:
        response = (
            f"🩺 Summary: You reported: {symptom_str}.\n"
            f"📊 Risk Level: {risk_level.upper()} ({risk_score:.1f}/10)\n"
            "💡 Suggested Action: Please consult a healthcare professional for assessment.\n"
            "⚠️ When To Seek Immediate Help: Worsening symptoms, difficulty breathing, or chest pain.\n\n"
            "⚠️ Disclaimer: This is NOT a diagnosis. Always consult a licensed physician."
        )
    else:
        # Append mandatory disclaimer after LLaMA's response
        response += (
            "\n\n⚠️ Disclaimer: This is a triage tool only, NOT a medical diagnosis. "
            "Always consult a licensed physician."
        )

    state["messages"].append({"role": "assistant", "content": response})
    return state
