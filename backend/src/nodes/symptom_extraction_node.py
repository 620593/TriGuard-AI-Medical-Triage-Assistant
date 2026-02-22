"""
symptom_extraction_node.py  (Version 3)
-----------------------------------------
LLaMA-based symptom extraction with multilingual support.

V3 changes:
    - Detects language from user input.
    - Translates non-English input to English for symptom extraction.
    - Stores original language in state for response translation.
"""

from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("symptom_extraction")


def symptom_extraction_node(state: TriageState) -> TriageState:
    """
    Extracts symptoms from user input with language detection.

    Args:
        state: Contains conversation messages.

    Returns:
        TriageState: Updated symptoms list and detected language.
    """
    user_messages = [m["content"] for m in state.get("messages", []) if m.get("role") == "user"]
    if not user_messages:
        return state

    latest_input = user_messages[-1]
    state["original_input"] = latest_input

    # ── Step 1: Language detection (if not already set by voice pipeline) ───────
    if not state.get("language") or state.get("language") == "en":
        lang_prompt = (
            "Detect the language of this text. Reply with ONLY the ISO 639-1 code "
            "(e.g., 'en', 'hi', 'es', 'fr', 'ar'). Nothing else.\n\n"
            f"Text: {latest_input}\n\nLanguage code:"
        )
        detected = call_llama(lang_prompt, max_tokens=5).strip().lower()

        # Validate: must be 2-3 chars, alphabetic
        if detected and len(detected) <= 3 and detected.isalpha():
            state["language"] = detected
        else:
            state["language"] = "en"

    # ── Step 2: Translate to English if needed ──────────────────────────────────
    english_input = latest_input
    if state.get("language", "en") != "en":
        translate_prompt = (
            f"Translate this to English. Return ONLY the translation.\n\n"
            f"Text: {latest_input}\n\nEnglish:"
        )
        translated = call_llama(translate_prompt, max_tokens=200).strip()
        if translated:
            english_input = translated

    # ── Step 3: Extract symptoms from English text ──────────────────────────────
    prompt = (
        "You are a medical symptom extractor. Your ONLY job is to list the symptoms "
        "mentioned by the patient. Do NOT add, infer, or invent symptoms.\n\n"
        "Output a comma-separated list of symptom phrases. "
        "If no symptoms are mentioned, output: none\n\n"
        f"Patient input: {english_input}\n\n"
        "Symptoms:"
    )

    raw = call_llama(prompt, max_tokens=100)

    if not raw or raw.strip().lower() == "none":
        return state

    extracted = [s.strip().lower() for s in raw.split(",") if s.strip()]

    # Merge with existing symptoms (union, no duplicates)
    existing = set(state.get("symptoms", []))
    state["symptoms"] = list(existing | set(extracted))

    log_event(logger, "symptoms_extracted",
              symptoms=state["symptoms"],
              language=state.get("language", "en"),
              count=len(extracted))

    return state
