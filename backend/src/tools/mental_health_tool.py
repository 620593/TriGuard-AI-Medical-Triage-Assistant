"""
mental_health_tool.py
---------------------
Detects mental-health crisis signals in user messages.

Why it exists:
    Self-harm or suicidal language requires immediate crisis guidance,
    overriding normal risk scoring. This tool performs a two-pass check:
      1. Fast keyword scan (catches obvious signals instantly).
      2. LLaMA confirmation pass (reduces false positives).

Input:
    messages (list[dict]): Full conversation history.

Returns:
    bool: True if a crisis signal is detected, False otherwise.
"""

from backend.src.tools.groq_llama_tool import call_llama

# Tier-1 keyword scan: fast O(n) check before calling LLaMA
_CRISIS_KEYWORDS = {
    "kill myself", "end my life", "suicide", "suicidal",
    "self-harm", "self harm", "cut myself", "want to die",
    "no reason to live", "hopeless", "can't go on",
}


def detect_mental_health_crisis(messages: list) -> bool:
    """
    Checks whether any message contains crisis or self-harm language.

    Args:
        messages (list[dict]): Conversation history with role/content pairs.

    Returns:
        bool: True if crisis language detected, False otherwise.
    """
    # Gather all user text (not assistant text) for analysis
    user_text = " ".join(
        m.get("content", "").lower()
        for m in messages
        if m.get("role") == "user"
    )

    # Pass 1: fast keyword match
    if any(kw in user_text for kw in _CRISIS_KEYWORDS):
        return True

    # Pass 2: LLaMA softcheck — catches paraphrased or implicit signals
    prompt = (
        "You are a mental health safety screener.\n"
        "Read the following user text and reply with ONLY 'YES' or 'NO'.\n"
        "Does the text contain any suggestion of self-harm, suicide, "
        "or a mental health crisis?\n\n"
        f"Text: {user_text[:800]}\n\nAnswer:"
    )
    answer = call_llama(prompt, max_tokens=5).strip().upper()

    # Accept 'YES' strictly to avoid false positives from LLaMA
    return answer.startswith("YES")
