"""
followup_node.py  (Version 5 — LLM-Driven Intelligent Follow-Up)
------------------------------------------------------------------
Integrates with followup_service for LLM-powered, ambiguity-aware questions.

V5 changes:
  - Uses followup_service.generate_followup_question() for intelligence.
  - MAX_FOLLOWUP_LOOPS = 3 (was 2 in V4).
  - Triggers on: symptom_extraction_failed OR ambiguous disease candidates.
  - On user's follow-up answer: merges context and clears pending_followup.
  - Uses response_formatter section structure for the question format.
  - History requests short-circuit: return history response immediately.

V4 preserved:
  - Emotional intelligence (distress words → calming prefix, now in service).
  - Language-aware question generation.
  - Loop budget guard.
"""

import asyncio
import re

from backend.src.services.followup_service import generate_followup_question, MAX_FOLLOWUP_LOOPS
from backend.src.services.history_service import is_history_request, get_history_response
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("followup")

MIN_SYMPTOMS = 2

# Question patterns that should NEVER trigger follow-up (general info questions)
_QUESTION_STARTERS = (
    "what ", "what's ", "what is ", "how ", "how do ", "how does ",
    "why ", "can you ", "tell me ", "explain ", "describe ", "define ",
    "is it ", "are there ", "do you ", "could you ", "would you ",
    "which ", "when ", "where ", "who ",
)
_EMERGENCY_BYPASS_HINTS = (
    "heart attack",
    "stroke",
    "cardiac arrest",
    "cannot breathe",
    "can't breathe",
    "difficulty breathing",
    "severe chest pain",
    "severe chronic disease",
)


def _is_general_question(text: str, symptoms: list) -> bool:
    """
    Returns True if the user's message is a general informational question
    with no real symptoms — follow-up should be skipped.
    """
    if not text:
        return False
    lower = text.lower().strip()
    # A question with no or minimal symptoms is likely general info
    no_symptoms = len(symptoms) == 0
    has_question_mark = "?" in lower
    starts_as_question = any(lower.startswith(q) for q in _QUESTION_STARTERS)
    # If 0 symptoms AND (starts with question word OR has ?) → skip followup
    return no_symptoms and (has_question_mark or starts_as_question)


def _has_emergency_phrase(text: str) -> bool:
    """Returns True if input includes known emergency-severity wording."""
    lower = (text or "").lower()
    return any(hint in lower for hint in _EMERGENCY_BYPASS_HINTS)


async def followup_node(state: TriageState) -> TriageState:
    """
    LLM-driven follow-up decision node.

    Decision tree:
      1. History request? → Fetch & return history immediately.
      2. User answered pending follow-up? → Clear + proceed.
      3. Max loops? → Proceed to pipeline.
      4. Symptoms sufficient + confidence high? → Proceed.
      5. Otherwise → Generate LLM follow-up question.

    Args:
        state: Current pipeline state.

    Returns:
        TriageState: Updated with follow-up question or cleared to proceed.
    """
    user_input     = (state.get("user_input", "") or "").strip()
    symptoms       = state.get("symptoms", []) or []
    followup_count = state.get("followup_count", 0)
    language       = state.get("language", "en")
    messages       = state.get("messages", []) or []
    disease_cands  = state.get("disease_candidates", []) or []
    confidence     = float((state.get("llm_output") or {}).get("confidence_score", 0.0))
    extraction_failed = state.get("symptom_extraction_failed", False)

    # ── Step 1: History request short-circuit ─────────────────────────────────
    user_id = state.get("user_id", "")
    if user_id and user_id != "anonymous" and is_history_request(user_input):
        history_response = await get_history_response(user_id)
        state["formatted_response"] = history_response
        state["final_response"]     = history_response
        state["next_action"]        = "history_response"
        state["messages"]           = messages + [{"role": "assistant", "content": history_response}]
        log_event(logger, "history_request_handled", user_id=user_id)
        return state

    # ── Step 2: User answered pending follow-up → clear and proceed ───────────
    if state.get("pending_followup") and not extraction_failed:
        log_event(logger, "followup_answered", followup_count=followup_count)
        state["pending_followup"] = ""
        state["next_action"] = ""
        return state

    # ── Step 3: Max loops exhausted → proceed to pipeline ────────────────────
    if followup_count >= MAX_FOLLOWUP_LOOPS:
        log_event(logger, "followup_max_loops_reached", count=followup_count)
        state["next_action"] = ""
        state["symptom_extraction_failed"] = False
        return state

    # ── Step 4: General question guard — skip follow-up ──────────────────────
    # If user asked a general info question (no symptoms, question format),
    # proceed directly to pipeline — no follow-up needed.
    if _is_general_question(user_input, symptoms):
        log_event(logger, "followup_skipped_general_question", user_input=user_input[:60])
        state["next_action"] = ""
        return state

    # ── Step 4.5: Emergency phrase guard — never block urgent flow with follow-up
    if _has_emergency_phrase(user_input):
        log_event(logger, "followup_skipped_emergency_phrase", user_input=user_input[:60])
        state["next_action"] = ""
        state["symptom_extraction_failed"] = False
        return state

    # ── Step 5: Enough symptoms + high confidence → proceed ──────────────────
    if len(symptoms) >= MIN_SYMPTOMS and confidence >= 0.7 and not extraction_failed:
        state["next_action"] = ""
        return state

    # ── Step 6: Generate LLM follow-up question ───────────────────────────────
    question, should_ask = await generate_followup_question(
        symptoms=symptoms,
        disease_candidates=disease_cands,
        followup_count=followup_count,
        language=language,
        messages=messages,
        confidence=confidence,
    )

    if not should_ask or not question:
        # Service decided no follow-up needed
        state["next_action"] = ""
        return state

    # Format follow-up as a clean chatbot section
    formatted_question = (
        "### ❓ A Quick Question\n\n"
        f"{question}\n\n"
        "---\n\n"
        "*Your answer will help me give you a more accurate assessment.*"
    )

    state["pending_followup"] = question
    state["messages"]         = messages + [{"role": "assistant", "content": formatted_question}]
    state["followup_count"]   = followup_count + 1
    state["next_action"]      = "ask_followup"

    # Return formatted question as the immediate response
    state["formatted_response"] = formatted_question
    state["final_response"]     = formatted_question

    log_event(logger, "followup_asked",
              loop=state["followup_count"],
              language=language,
              symptoms_count=len(symptoms))

    return state
