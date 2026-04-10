"""
emotional_detector.py
---------------------
Detects emotional distress in user input and provides calming response prefixes.

Used by response_node to add empathetic tone when the user expresses
fear, worry, panic, or anxiety. Pure functions only — no state mutation.
"""

from typing import Optional

# Emotional distress keywords (lowercase for matching)
_FEAR_KEYWORDS = frozenset({
    "afraid", "scared", "scary", "fear", "frightened", "terrified",
    "worried", "worrying", "worry", "anxious", "anxiety",
    "panic", "panicking", "panicked", "nervous",
    "stressed", "stress", "overwhelmed", "devastated",
    "crying", "helpless", "hopeless", "depressed",
    "freaking out", "going to die", "am i dying",
    "is it serious", "is this dangerous", "will i be okay",
    "what if", "can't stop thinking", "can't sleep",
})

# Calming prefixes matched to detected emotion category
_CALM_RESPONSES = {
    "fear": (
        "I understand this can feel really worrying, and it's completely "
        "natural to feel that way. Let's take this step by step together. "
    ),
    "panic": (
        "I hear you, and I want you to know that panicking is a normal "
        "response. Take a deep breath — I'm here to help you understand "
        "what's going on. "
    ),
    "anxiety": (
        "I can see this is causing you a lot of stress. That's completely "
        "understandable. Let me walk you through this calmly. "
    ),
    "sadness": (
        "I'm sorry you're feeling this way. You're not alone, and it's "
        "okay to feel upset. Let's look at this together. "
    ),
    "general": (
        "I understand your concern, and I appreciate you sharing this "
        "with me. Let's look at things calmly and clearly. "
    ),
}


def detect_emotion(text: str) -> Optional[str]:
    """
    Detects emotional distress category from user text.

    Args:
        text: Raw user input string.

    Returns:
        Emotion category ('fear', 'panic', 'anxiety', 'sadness', 'general')
        or None if no emotional distress detected.
    """
    if not text:
        return None

    lower = text.lower()

    # Check for specific emotion categories
    panic_words = {"panic", "panicking", "panicked", "freaking out", "going to die", "am i dying"}
    if any(word in lower for word in panic_words):
        return "panic"

    fear_words = {"afraid", "scared", "scary", "fear", "frightened", "terrified", "is it serious", "is this dangerous"}
    if any(word in lower for word in fear_words):
        return "fear"

    anxiety_words = {"anxious", "anxiety", "worried", "worrying", "worry", "nervous", "stressed", "stress", "overwhelmed", "can't stop thinking", "can't sleep"}
    if any(word in lower for word in anxiety_words):
        return "anxiety"

    sadness_words = {"crying", "helpless", "hopeless", "depressed", "devastated"}
    if any(word in lower for word in sadness_words):
        return "sadness"

    # Catch-all: check remaining keywords
    if any(word in lower for word in _FEAR_KEYWORDS):
        return "general"

    return None


def get_calming_prefix(emotion: str) -> str:
    """
    Returns a calming response prefix for the given emotion category.

    Args:
        emotion: Emotion category from detect_emotion().

    Returns:
        Calming prefix string, or empty string if no emotion.
    """
    if not emotion:
        return ""
    return _CALM_RESPONSES.get(emotion, _CALM_RESPONSES["general"])


def get_tone_instruction(risk_level: str) -> str:
    """
    Returns tone guidance based on risk level for LLM prompts.

    Args:
        risk_level: 'low', 'moderate', 'high', 'critical'

    Returns:
        Tone instruction string for the LLM.
    """
    level = (risk_level or "").lower()

    if level == "low":
        return (
            "TONE: Reassuring and warm. The situation appears manageable. "
            "Use phrases like 'this is usually nothing to worry about', "
            "'very common', 'should improve with simple care'. "
            "Do NOT use alarming language. Keep it casual and comforting."
        )
    elif level == "moderate":
        return (
            "TONE: Calm and informative. Suggest seeing a doctor without "
            "causing alarm. Use phrases like 'it would be a good idea to check with a doctor', "
            "'worth getting looked at'. Avoid words like 'dangerous', 'serious', 'emergency'."
        )
    elif level == "high":
        return (
            "TONE: Clear and direct but NOT scary. Convey urgency without "
            "panic. Use phrases like 'please see a doctor soon', "
            "'this needs medical attention'. Avoid catastrophizing."
        )
    elif level == "critical":
        return (
            "TONE: Urgent but calm. Guide the user to seek emergency help "
            "without causing panic. Use phrases like 'please go to the emergency room', "
            "'call for help now'. Be directive but compassionate."
        )
    else:
        return "TONE: Professional, warm, and reassuring."
