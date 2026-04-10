"""
symptom_extraction_node.py  (Version 5 — Hardened Extraction)
-----------------------------------------
LLaMA-based symptom extraction with multilingual support.

V5 changes (FIX #1 — Symptom Extraction Hardening):
    - Strict deterministic prompt: ONLY physical symptoms (pain, fever, cough…)
    - NEVER extracts: diseases (diabetes), treatments (medicine), meta-text
    - Validates output: removes multi-line, blacklisted words, caps to 5 items
    - Limits each phrase to 1–3 words
    - Triggers follow-up guard in state when too few valid symptoms

V4 changes (preserved):
    - Question-aware extraction: medical topics also populate symptoms list.
    - Multilingual: detects language, translates to English before extraction.
"""

import asyncio
import re

from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("symptom_extraction")

# FIX #1 — Blacklisted non-symptom words / topics the LLM tends to leak
_BLACKLIST = frozenset({
    "input", "output", "ready", "none", "unknown",
    # Diseases / diagnoses
    "diabetes", "hypertension", "cancer", "covid", "malaria", "tuberculosis",
    "asthma", "arthritis", "allergy", "anxiety", "depression", "migraine",
    # Treatments / nutrition
    "medicine", "medication", "nutrition", "diet", "tablet", "capsule",
    "paracetamol", "ibuprofen", "vitamin", "supplement", "syrup",
    # Meta-text
    "symptom", "symptoms", "problem", "health", "issue", "condition",
})

# Regex: only keep items that look like 1–3 word physical descriptors
_PHRASE_RE = re.compile(r"^[a-z][\w\s\-']{1,35}$")


def _validate_symptoms(raw_list: list[str]) -> list[str]:
    """
    FIX #1 — Post-extraction validation.
    - Removes blacklisted words
    - Removes phrases longer than 3 words
    - Removes single-char or very long entries
    - Caps to 5 items
    """
    cleaned: list[str] = []
    for phrase in raw_list:
        phrase = phrase.strip().lower()

        # Skip blanks and very short items
        if len(phrase) < 3:
            continue

        # Skip if any blacklisted word is a standalone word token in the phrase
        tokens = set(phrase.split())
        if tokens & _BLACKLIST:
            continue

        # Skip multi-word phrases beyond 3 words
        if len(phrase.split()) > 3:
            continue

        # Skip if phrase doesn't match basic alpha pattern
        if not _PHRASE_RE.match(phrase):
            continue

        cleaned.append(phrase)
        if len(cleaned) >= 5:  # FIX #12 — Hard cap at 5
            break

    return cleaned


async def symptom_extraction_node(state: TriageState) -> TriageState:
    """
    Extracts PHYSICAL symptoms from user input with language detection.

    V5: Strict prompt + post-extraction validation to prevent garbage data.
    Sets state['symptom_extraction_failed'] = True if < 2 valid symptoms found
    (used by followup_node to decide whether to ask a clarifying question).

    Args:
        state: Contains conversation messages.

    Returns:
        TriageState: Updated symptoms list and detected language.
    """
    user_messages = [m["content"] for m in state.get("messages", []) if m.get("role") == "user"]
    if not user_messages:
        state["symptom_extraction_failed"] = True
        return state

    latest_input = user_messages[-1]
    state["original_input"] = latest_input

    # FIX #12 — Garbage input guard: skip pipeline on trivially short input
    if len(latest_input.strip()) < 3:
        state["symptom_extraction_failed"] = True
        return state

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

    # ── Step 3: FIX #1 — Strict symptom-only extraction ────────────────────────
    # Deterministic prompt that ONLY extracts physical symptoms
    prompt = (
        "You are a medical symptom extractor.\n"
        "TASK: From the patient text below, extract ONLY physical symptoms.\n\n"
        "ALLOWED examples: fever, headache, chest pain, dry cough, nausea, sore throat, rash\n"
        "FORBIDDEN (never extract): disease names (diabetes, cancer), medications, "
        "nutrition advice, meta-text (input, output, ready), or anything not a physical sensation.\n\n"
        "OUTPUT FORMAT:\n"
        "- One single line\n"
        "- Comma-separated\n"
        "- All lowercase\n"
        "- Max 5 items\n"
        "- Each item: 1 to 3 words only\n"
        "- If nothing qualifies, output exactly: none\n\n"
        f"Patient text: {english_input}\n\n"
        "Physical symptoms:"
    )

    raw = await asyncio.to_thread(call_llama, prompt, max_tokens=80)

    # FIX #1 — Remove multi-line output (take only the first line)
    raw = raw.split("\n")[0].strip() if raw else ""

    if not raw or raw.strip().lower() == "none":
        state["symptom_extraction_failed"] = True
        log_event(logger, "symptoms_extracted",
                  symptoms=[],
                  language=state.get("language", "en"),
                  count=0)
        return state

    # Split, strip, lowercase
    raw_list = [s.strip().lower() for s in raw.split(",") if s.strip()]

    # FIX #1 — Validate: remove blacklisted, >3-word, and malformed phrases
    extracted = _validate_symptoms(raw_list)

    if not extracted:
        # Likely a medical question — fall back to topic extraction (V4 behaviour)
        question_prompt = (
            "The patient input appears to be a medical question, not a symptom description.\n"
            "Extract the core medical topic keywords (max 3, 1–2 words each).\n"
            "Output as comma-separated lowercase words. If unrelated to health: none\n\n"
            f"Patient input: {english_input}\n\nMedical topics:"
        )
        raw2 = await asyncio.to_thread(call_llama, question_prompt, max_tokens=50)
        raw2 = raw2.split("\n")[0].strip() if raw2 else ""
        if raw2 and raw2.lower() != "none":
            raw_list2 = [s.strip().lower() for s in raw2.split(",") if s.strip()]
            extracted = _validate_symptoms(raw_list2)

    # Merge with existing symptoms (union, no duplicates), cap at 5
    existing = list(state.get("symptoms", []))
    merged = list(dict.fromkeys(existing + extracted))[:5]  # FIX #12 — cap to 5
    state["symptoms"] = merged

    # FIX #2/#12 — Signal follow-up needed when fewer than 2 valid symptoms
    state["symptom_extraction_failed"] = len(merged) < 2

    log_event(logger, "symptoms_extracted",
              symptoms=state["symptoms"],
              language=state.get("language", "en"),
              count=len(extracted))

    return state
