"""
followup_service.py  (Version 1 — LLM-Driven Intelligent Follow-Up)
---------------------------------------------------------------------
LLM-powered follow-up question generator with self-loop control.

Features:
  - Analyzes extracted symptoms + possible disease candidates for ambiguity.
  - Generates targeted, intelligent clarifying questions (max 2 per round).
  - Self-loop control: MAX_FOLLOWUP_LOOPS = 3 (configurable).
  - Stop conditions:
      1. Confidence is sufficient (≥ 0.7).
      2. Max loops reached.
      3. No ambiguity detected.
  - All questions in user's detected language.
  - NEVER asks multiple overlapping questions about the same symptom.

Contract:
  - Input:  symptoms, disease_candidates, followup_count, language, messages
  - Output: (question: str | None, should_ask: bool)
"""

import asyncio
from typing import Optional

from backend.src.tools.groq_llama_tool import call_llama
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("followup_service")

# Central config
MAX_FOLLOWUP_LOOPS = 3
MIN_SYMPTOMS_FOR_CONFIDENT_RESPONSE = 2

# Diseases that typically need clarifying follow-ups
_AMBIGUOUS_DISEASE_KEYWORDS = {
    "migraine", "tension headache", "cluster headache",
    "ibs", "gastritis", "appendicitis",
    "angina", "gerd",
    "anxiety", "panic attack",
    "urinary tract infection", "kidney stone",
    "muscle strain", "fracture",
    "eczema", "psoriasis", "contact dermatitis",
}

_DISTRESS_WORDS = frozenset({
    "afraid", "scared", "worried", "panic",
    "panicking", "terrified", "fear", "anxious"
})

_CALMING_PREFIX = (
    "I understand this feels worrying — you're doing the right thing by checking. "
)


def _detect_ambiguity(symptoms: list, disease_candidates: list) -> bool:
    """
    Returns True if the symptom-disease combination has enough ambiguity
    to warrant a follow-up question.
    """
    if len(symptoms) < MIN_SYMPTOMS_FOR_CONFIDENT_RESPONSE:
        return True

    # Check if any candidate disease is in the ambiguous-disease set
    for disease in disease_candidates:
        disease_lower = str(disease).lower()
        if any(kw in disease_lower for kw in _AMBIGUOUS_DISEASE_KEYWORDS):
            return True

    return False


async def generate_followup_question(
    symptoms: list,
    disease_candidates: list,
    followup_count: int,
    language: str,
    messages: list,
    confidence: float = 0.0,
) -> tuple[Optional[str], bool]:
    """
    Generates an intelligent follow-up question using LLaMA.

    Returns:
        (question_text, should_ask) — where should_ask=False means skip follow-up.
    """
    # ── Guard 1: Max loops reached ───────────────────────────────────────────
    if followup_count >= MAX_FOLLOWUP_LOOPS:
        log_event(logger, "followup_max_loops_reached", count=followup_count)
        return None, False

    # ── Guard 2: High confidence already — no need to ask ───────────────────
    if confidence >= 0.7 and len(symptoms) >= MIN_SYMPTOMS_FOR_CONFIDENT_RESPONSE:
        log_event(logger, "followup_skipped_high_confidence", confidence=confidence)
        return None, False

    # ── Guard 3: No ambiguity detected ──────────────────────────────────────
    if not _detect_ambiguity(symptoms, disease_candidates):
        log_event(logger, "followup_skipped_no_ambiguity", symptoms=symptoms)
        return None, False

    # ── Build prompt for intelligent follow-up generation ───────────────────
    symptom_str = ", ".join(symptoms) if symptoms else "no clear symptoms yet"
    disease_str = ", ".join(str(d) for d in disease_candidates[:5]) if disease_candidates else "unclear"

    # Gather last 3 user messages for context
    user_history = [
        m.get("content", "") for m in messages
        if m.get("role") == "user"
    ][-3:]
    history_str = " | ".join(user_history) if user_history else "no prior context"

    # Previously asked questions (to avoid repetition)
    asked_questions = [
        m.get("content", "") for m in messages
        if m.get("role") == "assistant" and "?" in m.get("content", "")
    ][-3:]
    asked_str = " | ".join(asked_questions) if asked_questions else "none"

    lang_instruction = (
        f"IMPORTANT: Ask the question(s) in {language} language.\n"
        if language != "en"
        else ""
    )

    prompt = (
        "You are TriGuard AI — a calm, intelligent medical triage assistant.\n"
        f"{lang_instruction}\n"
        "Your task: Generate 1-2 targeted clarifying questions to help distinguish "
        "between the possible conditions. Be specific. Be warm. Avoid medical jargon.\n\n"
        f"Reported symptoms: {symptom_str}\n"
        f"Possible conditions: {disease_str}\n"
        f"Patient said: {history_str}\n"
        f"Already asked: {asked_str}\n\n"
        "RULES:\n"
        "- Ask questions that help NARROW DOWN the correct condition.\n"
        "- Do NOT repeat questions already asked.\n"
        "- Do NOT ask about symptoms already mentioned.\n"
        "- Maximum 2 questions. Number them 1. and 2.\n"
        "- Keep each question under 20 words.\n"
        "- Use friendly, calm language.\n"
        "- Never mention diagnosis or specific disease names to the user.\n\n"
        "Follow-up question(s):"
    )

    try:
        question = (await asyncio.to_thread(call_llama, prompt, max_tokens=100)).strip()
    except Exception as e:
        log_event(logger, "followup_llm_error", error=str(e))
        question = "Can you tell me more about your symptoms? How long have you been feeling this way?"

    if not question:
        question = "Can you describe your main symptom in a bit more detail? How long has this been going on?"

    # ── Apply calming prefix if user seems distressed ────────────────────────
    all_user_text = " ".join(user_history).lower()
    if any(word in all_user_text for word in _DISTRESS_WORDS):
        question = _CALMING_PREFIX + question

    log_event(logger, "followup_generated",
              loop=followup_count + 1,
              language=language,
              symptoms_count=len(symptoms))

    return question, True
