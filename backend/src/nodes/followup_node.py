"""
followup_node.py  (Version 3)
-------------------------------
Decides whether to ask clarifying questions, now with multilingual output.

V3 changes:
    - Follow-up questions generated in the user's detected language.
    - Structured logging of follow-up decisions.
"""

from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("followup")

MIN_SYMPTOMS = 2
HIGH_CONFIDENCE = 0.75


def followup_node(state: TriageState) -> TriageState:
    """
    Evaluates whether a clarifying question is needed before retrieval.

    Args:
        state: Current pipeline state.

    Returns:
        TriageState: Updated with follow-up question (if needed) and next_action.
    """
    symptoms = state.get("symptoms", [])
    followup_count = state.get("followup_count", 0)
    risk_confidence = state.get("risk_confidence", 0.0)
    language = state.get("language", "en")

    # Skip follow-up if already confident
    if risk_confidence >= HIGH_CONFIDENCE:
        state["next_action"] = ""
        return state

    # Proceed if enough symptoms OR budget exhausted
    if len(symptoms) >= MIN_SYMPTOMS or followup_count >= 3:
        state["next_action"] = ""
        return state

    # Build context-aware follow-up question
    symptom_str = ", ".join(symptoms) if symptoms else "no symptoms yet"
    history_turns = [
        m["content"] for m in state.get("messages", [])
        if m.get("role") == "user"
    ]
    patient_context = " | ".join(history_turns[-3:])

    # Generate in the user's language
    lang_instruction = ""
    if language != "en":
        lang_instruction = f"\nIMPORTANT: Ask the question in {language} language.\n"

    prompt = (
        "You are a medical triage assistant. Ask ONE short, clear clarifying question "
        "to better understand the patient's condition. Do NOT diagnose.\n"
        f"{lang_instruction}\n"
        f"Known symptoms: {symptom_str}\n"
        f"What patient said: {patient_context}\n\n"
        "Ask ONE focused question (max 20 words):"
    )

    question = call_llama(prompt, max_tokens=60).strip()

    if not question:
        question = "Can you describe your symptoms in more detail?"

    state["messages"].append({"role": "assistant", "content": question})
    state["followup_count"] = followup_count + 1
    state["next_action"] = "ask_followup"

    log_event(logger, "followup_asked",
              followup_count=state["followup_count"],
              language=language)

    return state
