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

import asyncio

logger = get_logger("symptom_extraction")


async def symptom_extraction_node(state: TriageState) -> TriageState:
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

    # ── Step 1: Language detection (skip if already explicitly provided) ───────
    # The route always sets state["language"] (default 'en').
    # Only run the extra LLM call if the input might be non-English AND
    # the language hasn't been determined yet by a prior step (e.g. voice).
    # Trigger detection only if lang code is absent or set to default 'en'
    # AND the input contains non-ASCII characters (likely non-English).
    current_lang = state.get("language", "")
    input_has_non_ascii = any(ord(c) > 127 for c in latest_input)
    needs_detection = (not current_lang or current_lang == "en") and input_has_non_ascii

    if needs_detection:
        lang_prompt = (
            "Detect the language of this text. Reply with ONLY the ISO 639-1 code "
            "(e.g., 'en', 'hi', 'es', 'fr', 'ar'). Nothing else.\n\n"
            f"Text: {latest_input}\n\nLanguage code:"
        )
        detected = (await asyncio.to_thread(call_llama, lang_prompt, max_tokens=5)).strip().lower()

        if detected and len(detected) <= 3 and detected.isalpha():
            state["language"] = detected
        else:
            state["language"] = "en"
    elif not current_lang:
        state["language"] = "en"

    # ── Step 2: Translate to English if needed ──────────────────────────────────
    english_input = latest_input
    if state.get("language", "en") != "en":
        translate_prompt = (
            f"Translate this to English. Return ONLY the translation.\n\n"
            f"Text: {latest_input}\n\nEnglish:"
        )
        translated = (await asyncio.to_thread(call_llama, translate_prompt, max_tokens=200)).strip()
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

    raw = await asyncio.to_thread(call_llama, prompt, max_tokens=100)

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
