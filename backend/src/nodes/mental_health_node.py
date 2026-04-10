"""
mental_health_node.py
---------------------
Handles two categories simultaneously:
  1. Emotional distress / mental health (calming, encouraging, safe messaging)
  2. Casual conversation (short friendly replies for greetings, disease questions,
     general health queries that are NOT symptom-driven)

This node is inserted BEFORE the medical pipeline for 'casual' intent.
It short-circuits to 'response' so the heavy medical nodes are skipped.

Output:
    state["next_action"] = "casual_response"  → response node picks up mental_health_text
    state["mental_health_text"]               → preformatted response text
    state["is_mental_health"]                 → True if distress detected
"""

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from backend.src.tools.groq_llama_tool import call_llama

logger = get_logger("mental_health")

# ── Distress keyword detection ─────────────────────────────────────────────────

_DISTRESS_KEYWORDS = frozenset({
    "scared", "terrified", "terrifying", "afraid", "fear", "panic",
    "anxious", "anxiety", "panic attack", "depressed", "depression",
    "hopeless", "worthless", "suicidal", "suicide", "kill myself",
    "end my life", "self-harm", "cutting", "can't cope", "cannot cope",
    "overwhelmed", "breaking down", "falling apart", "give up",
    "no reason to live", "don't want to live", "want to die",
    "can't go on", "cannot go on", "lonely", "alone", "lost",
    "crying", "sobbing", "devastated", "shattered", "empty",
    "help me", "please help", "i'm scared", "i am scared",
    "will i die", "am i dying", "going to die", "is it serious",
    "is it cancer", "is it fatal", "am i okay",
})

_CASUAL_GREETINGS = frozenset({
    "hello", "hi", "hey", "good morning", "good evening", "good afternoon",
    "how are you", "what can you do", "who are you", "what are you",
    "thanks", "thank you", "bye", "goodbye", "see you",
})


def _detect_distress(text: str) -> bool:
    """Returns True if the message contains emotional distress signals."""
    lower = text.lower()
    return any(kw in lower for kw in _DISTRESS_KEYWORDS)


def _is_greeting(text: str) -> bool:
    """Returns True if the message is a simple greeting/farewell."""
    lower = text.lower().strip()
    return any(lower.startswith(kw) or lower == kw for kw in _CASUAL_GREETINGS)


def _is_disease_question(text: str) -> bool:
    """
    Returns True if the user is asking about a disease/condition
    but NOT describing personal symptoms. Examples:
      'What is malaria?' — True   |   'I have malaria symptoms' — False
    """
    lower = text.lower()
    question_words = ("what", "how", "why", "can", "does", "is", "are",
                      "what's", "what is", "tell me about", "explain")
    has_question = any(lower.startswith(q) for q in question_words) or "?" in lower
    has_personal = any(kw in lower for kw in (
        "i have", "i am", "i feel", "my ", "i've been",
        "i'm having", "suffering from", "symptoms", "pain",
    ))
    return has_question and not has_personal


def mental_health_node(state: TriageState) -> TriageState:
    """
    Handles casual + mental health conversations.

    Decision tree:
      1. Emotional distress → calming + encouraging LLM response
      2. Greeting/farewell → short friendly reply (no LLM needed)
      3. Disease question  → short informational LLM reply
      4. Other casual      → short conversational LLM reply
    """
    user_messages = [
        m["content"] for m in state.get("messages", [])
        if m.get("role") == "user"
    ]
    user_text = user_messages[-1] if user_messages else ""

    is_distress = _detect_distress(user_text)
    is_greeting = _is_greeting(user_text)
    is_disease_q = _is_disease_question(user_text)

    state["is_mental_health"] = is_distress

    # ── Route 1: Pure greeting (no LLM) ────────────────────────────────────
    if is_greeting and not is_distress:
        log_event(logger, "mental_health_greeting", user_text=user_text[:60])
        state["mental_health_text"] = _greeting_response(user_text)
        state["next_action"] = "casual_response"
        return state

    # ── Route 2: Distress detected ─────────────────────────────────────────
    if is_distress:
        log_event(logger, "mental_health_distress_detected", user_text=user_text[:80])
        response = _generate_calming_response(state, user_text)
        state["mental_health_text"] = response
        state["next_action"] = "casual_response"
        return state

    # ── Route 3: Disease/health question ──────────────────────────────────
    if is_disease_q:
        log_event(logger, "mental_health_disease_question", user_text=user_text[:80])
        response = _generate_info_response(state, user_text)
        state["mental_health_text"] = response
        state["next_action"] = "casual_response"
        return state

    # ── Route 4: General casual ────────────────────────────────────────────
    log_event(logger, "mental_health_casual", user_text=user_text[:60])
    response = _generate_casual_response(state, user_text)
    state["mental_health_text"] = response
    state["next_action"] = "casual_response"
    return state


# ── Response generators ────────────────────────────────────────────────────────

def _greeting_response(user_text: str) -> str:
    """Static quick greeting response — no LLM needed."""
    text_lower = user_text.lower().strip()
    if any(kw in text_lower for kw in ("thanks", "thank you")):
        return (
            "You're very welcome! 😊 I'm here whenever you need help. "
            "Feel free to describe any symptoms, upload an image, or just chat."
        )
    if any(kw in text_lower for kw in ("bye", "goodbye", "see you")):
        return (
            "Take care and stay well! 💙 "
            "Remember — I'm here anytime you have health concerns."
        )
    # Default greeting
    return (
        "Hello! I'm TriGuard AI, your personal health screening assistant. 👋\n\n"
        "You can:\n"
        "• Describe your symptoms and I'll help assess them\n"
        "• Upload a medical image, X-ray, or document\n"
        "• Ask me about any health condition\n"
        "• Use voice mode to speak your symptoms\n\n"
        "How can I help you today?"
    )


def _generate_calming_response(state: TriageState, user_text: str) -> str:
    """Uses LLM to generate a warm, calming, encouraging response for distressed users."""
    prompt = f"""You are TriGuard AI — a warm, compassionate health assistant.

The user appears emotionally distressed or scared. Your role is to:
1. Acknowledge their feelings with empathy (1-2 sentences)
2. Reassure them calmly — they are not alone
3. Give 1-2 practical, gentle suggestions
4. Encourage them with positivity and courage
5. Gently offer to help with their health concern

CRITICAL RULES:
- NEVER diagnose or confirm serious conditions
- NEVER panic the user further
- Use calm, warm, friendly language — like a caring friend
- Keep the response SHORT (4-6 sentences max)
- NO bullet lists — write in natural, flowing sentences
- End with a positive, hopeful note

User's message: "{user_text}"

Respond naturally and warmly:"""

    try:
        response = call_llama(prompt, max_tokens=200)
        return response.strip() if response else _fallback_calming()
    except Exception as e:
        logger.warning(f"LLM calming response failed: {e}")
        return _fallback_calming()


def _generate_info_response(state: TriageState, user_text: str) -> str:
    """Short, friendly informational response for disease/health questions."""
    prompt = f"""You are TriGuard AI — a friendly, knowledgeable health assistant.

The user is asking a general health or disease question (not describing symptoms).

Answer in a helpful, conversational way:
- Give a brief, clear answer (3-5 sentences)
- Use plain everyday language — no medical jargon
- If relevant, suggest they describe their own symptoms for a more personalised assessment
- Be informative but not alarming
- Do NOT diagnose anyone

User's question: "{user_text}"

Respond naturally:"""

    try:
        response = call_llama(prompt, max_tokens=200)
        return response.strip() if response else _fallback_info()
    except Exception as e:
        logger.warning(f"LLM info response failed: {e}")
        return _fallback_info()


def _generate_casual_response(state: TriageState, user_text: str) -> str:
    """Short conversational response for general casual messages."""
    prompt = f"""You are TriGuard AI — a friendly health assistant.

The user has sent a casual message. Reply in a warm, natural, friendly way.
- Keep it SHORT (2-3 sentences)
- Be helpful, positive, and engaging
- Gently guide them toward sharing health concerns if appropriate
- Do NOT give medical advice for this casual message

User's message: "{user_text}"

Reply naturally:"""

    try:
        response = call_llama(prompt, max_tokens=150)
        return response.strip() if response else _fallback_casual()
    except Exception as e:
        logger.warning(f"LLM casual response failed: {e}")
        return _fallback_casual()


# ── Fallback responses (if LLM fails) ─────────────────────────────────────────

def _fallback_calming() -> str:
    return (
        "I hear you, and I want you to know — you're not alone in this. 💙 "
        "It's completely okay to feel worried or scared when it comes to health. "
        "Take a slow, deep breath. You've taken the right step by reaching out. "
        "Please share what's bothering you, and I'll do my best to help you understand and feel better. "
        "You've got this — and I'm right here with you. 🌟"
    )


def _fallback_info() -> str:
    return (
        "That's a great question! I'd love to help. "
        "Could you share a bit more about what you're wondering? "
        "If you have specific symptoms, I can give you a more personalised assessment."
    )


def _fallback_casual() -> str:
    return (
        "I'm here and happy to help! 😊 "
        "Feel free to describe any symptoms, upload an image, or ask me anything health-related."
    )
