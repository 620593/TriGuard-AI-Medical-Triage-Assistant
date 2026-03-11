"""
language_utils.py
-----------------
Helpers for normalizing user-facing language names to ISO 639-1 codes.
"""

from typing import Optional


_LANGUAGE_ALIASES = {
    "en": "en",
    "english": "en",
    "hi": "hi",
    "hindi": "hi",
    "es": "es",
    "spanish": "es",
    "fr": "fr",
    "french": "fr",
    "de": "de",
    "german": "de",
    "it": "it",
    "italian": "it",
    "pt": "pt",
    "portuguese": "pt",
    "bn": "bn",
    "bengali": "bn",
    "ta": "ta",
    "tamil": "ta",
    "te": "te",
    "telugu": "te",
    "mr": "mr",
    "marathi": "mr",
    "gu": "gu",
    "gujarati": "gu",
    "kn": "kn",
    "kannada": "kn",
    "ml": "ml",
    "malayalam": "ml",
    "pa": "pa",
    "punjabi": "pa",
    "ur": "ur",
    "urdu": "ur",
}


def normalize_language_code(language: Optional[str], default: str = "en") -> str:
    """Normalizes a language name or code to a gTTS-compatible ISO 639-1 code."""
    if not language:
        return default

    normalized = str(language).strip().lower()
    if not normalized:
        return default

    return _LANGUAGE_ALIASES.get(normalized, normalized[:2] if len(normalized) > 2 else normalized)