"""
symptom_extraction_node.py  (Version 4 — Question-Aware Extraction)
-----------------------------------------
LLaMA-based symptom extraction with multilingual support.

V4 changes:
    - Now handles two input types:
        1. Symptom descriptions: "I have fever and headache" → extracts symptoms
        2. Medical questions: "what causes back pain?" → extracts medical topics
      Both types populate state["symptoms"] so disease_retrieval and Tavily fire.
    - Prevents the pipeline from short-circuiting on question-type inputs.

V3 changes (preserved):
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
    Extracts symptoms or medical topics from user input with language detection.

    V4: If the input is a medical question (not a symptom description),
    extracts the medical topic keywords so downstream nodes have context to
    retrieve relevant disease/medical info from the knowledge base.

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

    # ── Step 1: Language detection ──────────────────────────────────────────────
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

    # ── Step 3: Extract symptoms OR medical topics ──────────────────────────────
    # V4: Single prompt handles both symptom descriptions and medical questions.
    # For questions, extracts the medical topic(s) so downstream nodes fire.
    prompt = (
        "You are a medical information extractor. Given the patient input below, extract:\n"
        "- If the patient DESCRIBES symptoms (e.g. 'I have fever'): list the symptom keywords.\n"
        "- If the patient ASKS A QUESTION about a medical topic (e.g. 'what causes headaches?', "
        "'is fever dangerous?', 'tell me about diabetes'): list the medical topic keywords.\n\n"
        "Output a comma-separated list of medical keyword phrases (max 5).\n"
        "Do NOT add, infer, or invent anything not mentioned.\n"
        "If completely unrelated to health/medicine, output: none\n\n"
        f"Patient input: {english_input}\n\n"
        "Medical keywords:"
    )

    raw = await asyncio.to_thread(call_llama, prompt, max_tokens=120)

    if not raw or raw.strip().lower() == "none":
        return state

    extracted = [s.strip().lower() for s in raw.split(",") if s.strip() and len(s.strip()) > 2]

    if not extracted:
        return state

    # Merge with existing symptoms (union, no duplicates)
    existing = set(state.get("symptoms", []))
    state["symptoms"] = list(existing | set(extracted))

    log_event(logger, "symptoms_extracted",
              symptoms=state["symptoms"],
              language=state.get("language", "en"),
              count=len(extracted))

    return state
