"""
symptom_validator.py
--------------------
Validates and sanitizes LLM-extracted symptom strings.

Prevents corrupted LLM output (meta-responses, prompt leakage,
multi-line garbage) from entering state["symptoms"].

Rules:
    - Max 4 words per symptom phrase.
    - Must not contain prompt-leaked phrases.
    - Must not be a multi-line blob.
    - Must not be a generic medical topic (treatment, disease, diabetes…)
    - Strips non-alpha characters except spaces and hyphens.
    - Returns only clean, short physical symptom keyword phrases.
"""

import re
from typing import List

# Phrases that indicate LLM meta-response (NOT real symptoms)
_GARBAGE_PHRASES = frozenset({
    "i'm ready", "i will", "i am ready", "what's the input",
    "follow the rules", "let me", "here is", "output:",
    "input:", "sure", "certainly", "of course", "as an ai",
    "i cannot", "i can't", "note:", "please provide",
    "i'll", "based on", "the symptoms are", "the input is",
    "i understand", "here are", "ready to extract",
    "i will follow", "strictly", "what causes",
})

# Fix 3: Medical topic words that are NOT physical symptoms.
# These are categories / concepts, not things a patient physically experiences.
_INVALID_TERMS = frozenset({
    # Treatment / process terms
    "treatment", "medicine", "medicines", "medication", "medications",
    "therapy", "therapies", "remedy", "remedies", "cure", "surgery",
    "prescription", "dose", "dosage", "drug", "drugs", "supplement",
    "supplements", "vitamin", "vitamins",
    # Condition / disease label terms (topics, not felt symptoms)
    "disease", "disorder", "condition", "syndrome", "illness",
    "infection", "diabetes", "cancer", "hypertension",
    # Nutrition / lifestyle topics
    "nutrition", "diet", "exercise", "lifestyle", "food", "foods",
    # Generic medical meta-concepts
    "symptom", "symptoms", "cause", "causes", "effect", "effects",
    "risk", "risks", "prevention", "diagnosis",
})

# Regex: only letters, spaces, hyphens allowed (strip everything else)
_CLEAN_RE = re.compile(r"[^a-zA-Z\s\-]")

# Max words allowed in a single symptom phrase
_MAX_WORDS = 4

# Minimum length for a symptom string to be valid
_MIN_LEN = 2


def _is_invalid_term(text: str) -> bool:
    """Returns True if text is a generic medical topic rather than a physical symptom."""
    lower = text.lower().strip()
    # Exact match
    if lower in _INVALID_TERMS:
        return True
    # Phrase whose ONLY words are all blacklisted (e.g. "diabetes treatment")
    words = set(lower.split())
    if words and words.issubset(_INVALID_TERMS):
        return True
    return False


def _is_garbage(text: str) -> bool:
    """Returns True if text looks like LLM meta-response rather than a symptom."""
    lower = text.lower().strip()
    # Check exact matches and substring matches against garbage phrases
    for phrase in _GARBAGE_PHRASES:
        if phrase in lower:
            return True
    # Multi-line text is garbage (symptoms are single short phrases)
    if "\n" in text:
        return True
    # More than _MAX_WORDS → probably a sentence, not a keyword
    if len(lower.split()) > _MAX_WORDS:
        return True
    return False


def validate_symptoms(raw_symptoms: List[str]) -> List[str]:
    """
    Filters and cleans a list of raw symptom strings.

    Args:
        raw_symptoms: Raw symptom strings from LLM extraction.

    Returns:
        List of clean, validated symptom keywords (1-4 words each).
    """
    validated = []
    seen = set()

    for raw in raw_symptoms:
        if not isinstance(raw, str):
            continue

        # Strip whitespace and clean non-alpha chars
        cleaned = _CLEAN_RE.sub("", raw).strip().lower()

        # Skip empty or too-short
        if len(cleaned) < _MIN_LEN:
            continue

        # Skip garbage / meta-responses
        if _is_garbage(cleaned):
            continue

        # Fix 3: Skip generic medical topic terms (not physical symptoms)
        if _is_invalid_term(cleaned):
            continue

        # Skip duplicates (case-insensitive)
        if cleaned in seen:
            continue

        seen.add(cleaned)
        validated.append(cleaned)

    return validated[:10]  # Hard cap at 10 symptoms
