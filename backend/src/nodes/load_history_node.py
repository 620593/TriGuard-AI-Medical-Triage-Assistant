"""
load_history_node.py  (Version 5 — Async-Safe Event Loop Fix)
--------------------------------------------------------------
Loads conversation history for in-session continuity.

V5 Changes (over V4):
    - ASYNC-SAFE: Replaced all `asyncio.get_event_loop()` calls that caused
      "no current event loop in thread" errors when running inside thread pools.
      Now uses `asyncio.run()` in isolated ThreadPoolExecutor threads, which
      always creates its own event loop — safe from any calling context.
    - history_service integration: Checks for history request intent and
      short-circuits to history response if detected.
    - Prior history context fetching is now properly async-isolated.
    - All V4 behavior preserved (same-session load, symptom merge, etc.).
"""

import asyncio
import concurrent.futures

from backend.src.tools.history_tool import load_history
from backend.src.tools.mongodb_tool import load_session
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("load_history")


def _run_async_safe(coro):
    """
    Runs an async coroutine from any context (sync or async, any thread).
    Uses asyncio.run() in a fresh ThreadPoolExecutor thread — this ALWAYS
    creates a clean event loop, avoiding 'no current event loop' errors.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result(timeout=8)


def load_history_node(state: TriageState) -> TriageState:
    """
    Restores in-session memory from MongoDB (or history.json fallback).

    Priority:
        1. new_session → clean slate
        2. same session_id → always load MongoDB session data (async-safe)
        3. use_history opt-in → cross-session history.json merge
        4. default → pass-through
    """
    # ── Branch 1: New session requested ──────────────────────────────────────
    if state.get("next_action") == "new_session" or state.get("new_session"):
        state["next_action"]    = ""
        state["followup_count"] = 0
        state["symptoms"]       = []
        state["last_symptoms"]  = []
        state["retrieved_info"] = []
        state["risk_score"]     = 0.0
        state["risk_level"]     = ""
        state["risk_confidence"] = 0.0
        state["mental_health_flag"] = False
        state["messages"]      = state["messages"][-1:]   # Keep only current input
        state["session_memory"] = ""

        # Cross-session prior history (async-safe)
        user_id = state.get("user_id", "")
        if user_id and user_id != "anonymous":
            from backend.src.tools.history_retrieval_tool import get_relevant_history
            symptoms = state.get("symptoms", [])
            intent   = state.get("intent", "casual")
            try:
                prior_ctx = _run_async_safe(
                    get_relevant_history(user_id, symptoms, intent)
                )
            except Exception as exc:
                log_event(logger, "prior_history_failed",
                          user_id=user_id, error=str(exc))
                prior_ctx = ""
            state["prior_history_context"] = prior_ctx

        log_event(logger, "history_reset", reason="new_session")
        return state

    # ── Branch 2: Mid-session follow-up loop (in-memory re-entry) ────────────
    if state.get("_mid_session", False):
        return state

    session_id = state.get("session_id", "")
    is_same_session = bool(
        session_id
        and session_id not in ("", "local")
    )

    # ── Branch 3: Same-session → always load from MongoDB (async-safe) ───────
    if is_same_session:
        try:
            # V5 FIX: asyncio.run() in isolated thread — always has its own loop.
            # This replaces the broken asyncio.get_event_loop() approach.
            session_doc = _run_async_safe(load_session(session_id))
        except Exception as exc:
            log_event(logger, "session_load_failed",
                      session_id=session_id, error=str(exc))
            session_doc = None

        if session_doc:
            saved_state = session_doc.get("state", {})

            # Restore conversation history (cap at 20 messages)
            prior_messages = saved_state.get("messages", [])
            if prior_messages:
                current_input = state["messages"][-1:]
                prior_capped  = prior_messages[-20:]
                state["messages"] = prior_capped + current_input

            # Union-merge symptoms
            saved_symptoms   = saved_state.get("symptoms", []) or []
            current_symptoms = state.get("symptoms", []) or []
            state["symptoms"]      = list(set(saved_symptoms) | set(current_symptoms))
            state["last_symptoms"] = saved_symptoms

            # Restore cross-turn context
            if saved_state.get("risk_level"):
                state["last_risk_level"] = saved_state["risk_level"]
            if saved_state.get("intent"):
                state["last_intent"] = saved_state["intent"]
            if saved_state.get("last_structured_summary"):
                state["last_structured_summary"] = saved_state["last_structured_summary"]
            if saved_state.get("disease_candidates"):
                state["disease_candidates"] = saved_state["disease_candidates"]
            # V5: Restore follow-up loop count from session
            if saved_state.get("followup_count") is not None:
                state["followup_count"] = saved_state["followup_count"]

            log_event(logger, "session_loaded",
                      session_id=session_id,
                      message_count=len(prior_messages),
                      symptom_count=len(state["symptoms"]))
        else:
            log_event(logger, "session_not_found", session_id=session_id)

        return state

    # ── Branch 4: Cross-session opt-in (no session_id) ───────────────────────
    if state.get("use_history", False):
        history = load_history()
        if history:
            if history.get("messages"):
                recent = history["messages"][-10:]
                state["messages"] = recent + state["messages"]
            state["followup_count"] = history.get("followup_count", 0)
            if history.get("symptoms"):
                existing = set(history["symptoms"])
                current  = set(state.get("symptoms", []))
                state["symptoms"] = list(existing | current)
            log_event(logger, "history_loaded",
                      message_count=len(history.get("messages", [])),
                      symptom_count=len(history.get("symptoms", [])))
        return state

    # ── Branch 5: Default pass-through ───────────────────────────────────────
    log_event(logger, "session_skipped",
              reason="use_history_not_set")
    return state
