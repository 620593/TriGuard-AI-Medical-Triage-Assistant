"""
classification_node.py
-----------------------
Intent classification node for TriGuard AI.

Determines the user's intent based on input_mode and message content.
Routes to the correct pipeline early to avoid unnecessary computation.

Intents:
    - medical_text   : Text-based symptom description
    - medical_report : Uploaded medical report image (OCR pipeline)
    - xray           : Uploaded X-ray image
    - body_image     : Uploaded body/skin image
    - casual         : Casual conversation or mental health concern

This node does NOT call an LLM. It uses deterministic rules based on
input_mode and lightweight keyword matching for text classification.

# 🔥 V5.1 FOLLOW-UP CONTEXT PATCH:
    - For text/voice turns, always sets state["user_input"] from the
      latest user message.
    - If the message is empty but last_structured_summary exists
      (e.g., prior X-ray or image analysis), falls back to the summary
      so llm_brain always has non-empty context to reason about.
"""

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("classification")

# Keywords that suggest casual / mental health conversation
_CASUAL_KEYWORDS = frozenset({
    "hello", "hi", "hey", "thanks", "thank you", "bye", "goodbye",
    "how are you", "what are you", "who are you", "what can you do",
})

_MENTAL_KEYWORDS = frozenset({
    "depressed", "depression", "suicidal", "suicide", "kill myself",
    "end my life", "hopeless", "worthless", "self-harm", "cutting",
    "anxiety", "panic attack", "lonely", "no reason to live",
    "don't want to live", "want to die", "can't go on",
})

# Medical keywords that confirm medical_text intent
_MEDICAL_KEYWORDS = frozenset({
    "pain", "ache", "fever", "cough", "headache", "nausea", "vomit",
    "dizziness", "swelling", "rash", "bleeding", "breathless",
    "chest pain", "stomach", "diarrhea", "fatigue", "weakness",
    "sore throat", "infection", "symptoms", "condition", "diagnosis",
    "medicine", "prescri", "treatment", "doctor", "hospital",
})


def classification_node(state: TriageState) -> TriageState:
    """
    Classifies user intent based on input_mode and message content.

    Routing logic (deterministic, no LLM):
        1. input_mode == 'xray'   → intent = 'xray'
        2. input_mode == 'image'  → check image_type hint:
           - If report/document → 'medical_report'
           - Otherwise          → 'body_image'
        3. input_mode == 'text' or 'voice' → keyword analysis:
           - Mental health keywords → 'casual' (mental health pipeline)
           - Short casual greetings → 'casual'
           - Default fallback       → 'medical_text' (safest assumption)

    # 🔥 V5.1 FOLLOW-UP CONTEXT PATCH:
        For text/voice turns, always sets state['user_input'] to the latest
        user message. If that message is empty and a prior analysis exists
        (last_structured_summary), falls back to summary for context bridging.

    Args:
        state: Contains input_mode, messages, and optional image metadata.

    Returns:
        TriageState: With state["intent"] and state["user_input"] populated.
    """
    input_mode = state.get("input_mode", "text")

    # ── Image-based routing (deterministic by mode) ─────────────────────────
    if input_mode == "xray":
        state["intent"] = "xray"
        log_event(logger, "intent_classified", intent="xray", source="input_mode")
        return state

    if input_mode == "image":
        # Check if this is a medical report or body image.
        # Use image_type_hint from frontend if available.
        # The broader the synonym set, the more frequently we can skip
        # the Vision → OCR double-processing path (V4.1 performance note).
        image_type_hint = state.get("image_type_hint", "").lower()
        _REPORT_HINTS = frozenset({
            "report", "prescription", "document", "lab_report",
            "medical_record", "lab", "labs", "letter", "text", "form",
            "invoice", "doc", "note", "notes", "clinical_note",
        })
        if image_type_hint in _REPORT_HINTS:
            state["intent"] = "medical_report"
        else:
            state["intent"] = "body_image"

        log_event(logger, "intent_classified",
                  intent=state["intent"], source="input_mode_image")
        return state

    # ── Text/voice routing (keyword-based, no LLM) ─────────────────────────
    user_messages = [
        m["content"] for m in state.get("messages", [])
        if m.get("role") == "user"
    ]
    latest_input = user_messages[-1].lower().strip() if user_messages else ""

    # 🔥 V5.1 FOLLOW-UP CONTEXT PATCH: always populate user_input for text turns.
    # This guarantees llm_brain never receives an empty user_input on text turns.
    if latest_input:
        state["user_input"] = latest_input
    elif state.get("last_structured_summary"):
        # Prior image/xray analysis exists — treat summary as implicit context.
        # llm_brain will detect this and use combined_input (PATCH 3).
        state["user_input"] = ""   # intentionally empty: PATCH 3 picks it up
        log_event(logger, "classification_context_bridge",
                  reason="empty_input_with_prior_summary")
    # else: no text and no prior summary — llm_brain safety guard handles it

    # Check mental health keywords first (safety-critical)
    if any(kw in latest_input for kw in _MENTAL_KEYWORDS):
        state["intent"] = "casual"
        log_event(logger, "intent_classified",
                  intent="casual", source="mental_keywords")
        return state

    # Check casual greetings
    if any(latest_input.startswith(kw) or latest_input == kw
           for kw in _CASUAL_KEYWORDS):
        # Only classify as casual if the message is SHORT (< 30 chars)
        # Longer messages with greetings like "Hi, I have chest pain" are medical
        if len(latest_input) < 30:
            state["intent"] = "casual"
            log_event(logger, "intent_classified",
                      intent="casual", source="casual_keywords")
            return state

    # Default: medical text
    state["intent"] = "medical_text"
    log_event(logger, "intent_classified",
              intent="medical_text", source="default")
    return state
