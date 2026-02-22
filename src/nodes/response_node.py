"""
response_node.py
----------------
Generates the final triage response for the user.

Hard rules:
  - MUST reference retrieved_info (no hallucination).
  - MUST NOT give a diagnosis.
  - MUST NOT prescribe medication.
  - If next_action == 'priority_interrupt', prepend an emergency alert.
  - If next_action == 'ask_followup', return the last follow-up question.
"""

from src.state.state import TriageState


def response_node(state: TriageState) -> TriageState:
    """
    Builds a safe, grounded triage response from state data.

    Why it exists:
        The final message to the user must be clinically responsible —
        grounded in retrieved_info, informative without diagnosing,
        and always directing the user toward professional medical care.

    Args:
        state (TriageState): Fully populated state from all prior nodes.

    Returns:
        TriageState: State with the assistant's final response appended to messages.
    """
    next_action = state.get("next_action", "")
    risk_level = state.get("risk_level", "unknown")
    risk_score = state.get("risk_score", 0.0)
    symptoms = state.get("symptoms", [])
    retrieved_info = state.get("retrieved_info", [])
    messages = state.get("messages", [])

    # --- Case 1: Still waiting for more user input ---
    if next_action == "ask_followup":
        # The follow-up question is already the last assistant message added by
        # symptom_followup_node or risk_evaluation_node. Nothing more to generate.
        return state

    # --- Case 2: Priority interrupt — critical emergency detected ---
    if next_action == "priority_interrupt":
        alert = (
            "🚨 URGENT MEDICAL ALERT 🚨\n\n"
            f"Based on the symptoms you described ({', '.join(symptoms)}), "
            "the information we retrieved indicates a potentially life-threatening situation.\n\n"
            "⚡ Please call emergency services (911 / 999 / 112) IMMEDIATELY "
            "or go to the nearest emergency room right away.\n\n"
            "Do not wait or self-medicate. This is a triage assistant, not a doctor."
        )
        state["messages"].append({"role": "assistant", "content": alert})
        return state

    # --- Case 3: Standard grounded triage response ---

    # Build context summary from Tavily results (source of truth only)
    context_lines = []
    for i, info in enumerate(retrieved_info[:3], start=1):
        # Truncate long snippets to keep the response readable
        snippet = info[:300] + "..." if len(info) > 300 else info
        context_lines.append(f"  {i}. {snippet}")

    context_block = (
        "\n".join(context_lines)
        if context_lines
        else "  No specific medical information was retrieved for your symptoms."
    )

    # Map risk level to readable user guidance
    guidance_map = {
        "low": (
            "Your reported symptoms appear to be at a LOW risk level. "
            "Monitor your condition and consult a doctor if symptoms worsen or persist."
        ),
        "moderate": (
            "Your reported symptoms appear to be at a MODERATE risk level. "
            "We recommend scheduling a medical appointment soon and avoiding self-medication."
        ),
        "high": (
            "Your reported symptoms appear to be at a HIGH risk level. "
            "Please seek medical attention TODAY. Visit an urgent care clinic or call your doctor."
        ),
        "critical": (
            "Your reported symptoms appear to be at a CRITICAL risk level. "
            "Please go to an emergency room or call emergency services NOW."
        ),
    }
    guidance = guidance_map.get(risk_level, "Please consult a healthcare professional.")

    # Compose the full response
    symptom_str = ", ".join(symptoms) if symptoms else "the symptoms you described"
    response = (
        f"Based on what you've shared ({symptom_str}), here is what our medical "
        f"triage assistant found:\n\n"
        f"📊 Risk Assessment: {risk_level.upper()} (Score: {risk_score:.1f}/10)\n\n"
        f"📋 Relevant Medical Context (from search results):\n{context_block}\n\n"
        f"💡 Triage Guidance:\n{guidance}\n\n"
        "⚠️ DISCLAIMER: This is NOT a diagnosis. This tool does not replace "
        "professional medical advice. Always consult a licensed physician for any health concern."
    )

    state["messages"].append({"role": "assistant", "content": response})
    return state
