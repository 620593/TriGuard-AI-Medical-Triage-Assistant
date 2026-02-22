"""
followup_node.py  (Version 2)
-------------------------------
Decides whether to ask a clarifying question or proceed to retrieval.

Logic:
  - If symptoms unclear (< 2 extracted) AND followup_count < 3 → ask LLaMA question.
  - If risk_confidence >= 0.75 on a prior turn → skip follow-up (enough info).
  - Otherwise → proceed to Tavily retrieval.

LLaMA generates context-aware questions (not static templates like V1).

Input:
    state (TriageState): Contains symptoms, followup_count, messages, risk_confidence.

Returns:
    TriageState: Possibly with a follow-up question added to messages and
                 next_action set to 'ask_followup'.
"""

from src.tools.groq_llama_tool import call_llama
from src.state.state import TriageState

MIN_SYMPTOMS = 2             # Minimum distinct symptoms before we feel confident
HIGH_CONFIDENCE = 0.75       # If already confident enough, skip follow-up


def followup_node(state: TriageState) -> TriageState:
    """
    Evaluates whether a clarifying question is needed before retrieval.

    Args:
        state (TriageState): Current pipeline state.

    Returns:
        TriageState: State updated with follow-up question (if needed) and next_action.
    """
    symptoms = state.get("symptoms", [])
    followup_count = state.get("followup_count", 0)
    risk_confidence = state.get("risk_confidence", 0.0)

    # Skip follow-up if we already have high confidence from a prior turn
    if risk_confidence >= HIGH_CONFIDENCE:
        state["next_action"] = ""
        return state

    # Proceed if we have enough symptoms OR exhausted the follow-up budget
    if len(symptoms) >= MIN_SYMPTOMS or followup_count >= 3:
        state["next_action"] = ""
        return state

    # Build context for LLaMA so the question is relevant, not generic
    symptom_str = ", ".join(symptoms) if symptoms else "no symptoms yet"
    history_turns = [
        m["content"] for m in state.get("messages", [])
        if m.get("role") == "user"
    ]
    patient_context = " | ".join(history_turns[-3:])   # Last 3 user messages

    prompt = (
        "You are a medical triage assistant. Ask ONE short, clear clarifying question "
        "to better understand the patient's condition. Do NOT diagnose.\n\n"
        f"Known symptoms: {symptom_str}\n"
        f"What patient said: {patient_context}\n\n"
        "Ask ONE focused question (max 20 words):"
    )

    question = call_llama(prompt, max_tokens=60).strip()

    # Fallback if LLaMA returns nothing
    if not question:
        question = "Can you describe your symptoms in more detail?"

    # Append to conversation and update state
    state["messages"].append({"role": "assistant", "content": question})
    state["followup_count"] = followup_count + 1
    state["next_action"] = "ask_followup"

    return state
