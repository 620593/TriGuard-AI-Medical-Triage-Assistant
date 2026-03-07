"""
load_history_node.py  (Version 4 — In-Session Persistent Memory)
------------------------------------------------------------------
Loads conversation history for in-session continuity.

V4 Changes (over V3):
    - SAME-SESSION auto-load: When session_id is present AND new_session is NOT set,
      history is ALWAYS loaded from MongoDB — regardless of use_history flag.
      This gives every follow-up message full context of the current session.
    - use_history flag now controls only CROSS-SESSION (separate session IDs) history.
    - Merged messages capped at last 20 to keep context window lean.
    - Symptoms are UNION-merged from session history into current state.
    - last_symptoms, last_risk_level, last_intent, disease_candidates, and
      last_structured_summary are all restored from the saved session document.

Four behaviours:
  1. new_session=True              → Wipe fields; return clean state.
  2. session_id present (no new)  → Load session from MongoDB (always).
  3. use_history=True (no sid)    → Load history.json cross-session fallback.
  4. Default (no sid, no opt-in)  → Pure pass-through.
"""

import asyncio

from backend.src.tools.history_tool import load_history
from backend.src.tools.mongodb_tool import load_session
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("load_history")


def load_history_node(state: TriageState) -> TriageState:
    """
    Restores in-session memory from MongoDB (or history.json fallback).

    Priority:
        1. new_session → clean slate
        2. same session_id → always load MongoDB session data
        3. use_history opt-in → cross-session history.json merge
        4. default → pass-through
    """
    # ── Branch 1: New session requested ─────────────────────────────────────
    if state.get("next_action") == "new_session" or state.get("new_session"):
        state["next_action"] = ""
        state["followup_count"] = 0
        state["symptoms"] = []
        state["last_symptoms"] = []
        state["retrieved_info"] = []
        state["risk_score"] = 0.0
        state["risk_level"] = ""
        state["risk_confidence"] = 0.0
        state["mental_health_flag"] = False
        state["messages"] = [state["messages"][-1]]   # Keep only current input
        state["session_memory"] = ""
        
        # Cross-Session History Retrieval (Long-Term Memory)
        user_id = state.get("user_id", "")
        if user_id and user_id != "anonymous":
            from backend.src.tools.history_retrieval_tool import get_relevant_history
            symptoms = state.get("symptoms", [])
            intent = state.get("intent", "casual")
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(asyncio.run, get_relevant_history(user_id, symptoms, intent))
                        prior_ctx = future.result(timeout=5)
                else:
                    prior_ctx = loop.run_until_complete(get_relevant_history(user_id, symptoms, intent))
            except Exception as exc:
                log_event(logger, "prior_history_failed", user_id=user_id, error=str(exc))
                prior_ctx = ""
            state["prior_history_context"] = prior_ctx

        log_event(logger, "history_reset", reason="new_session")
        return state

    # ── Branch 2: Mid-session follow-up loop (in-memory re-entry) ────────────
    if state.get("_mid_session", False):
        return state

    session_id = state.get("session_id", "")
    is_same_session = bool(session_id and session_id != "local" and session_id != "")

    # ── Branch 3: Same-session → always load from MongoDB ────────────────────
    if is_same_session:
        try:
            # Run the async load_session in a sync context safely
            # (load_history_node is a sync node in the graph)
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — use asyncio.ensure_future trick
                # by running in its own thread to avoid blocking the event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, load_session(session_id))
                    session_doc = future.result(timeout=5)
            else:
                session_doc = loop.run_until_complete(load_session(session_id))
        except Exception as exc:
            log_event(logger, "session_load_failed", session_id=session_id, error=str(exc))
            session_doc = None

        if session_doc:
            saved_state = session_doc.get("state", {})

            # Restore conversation history (cap at 20 messages)
            prior_messages = saved_state.get("messages", [])
            if prior_messages:
                # Prepend saved messages, keeping current user message at end
                current_input = state["messages"][-1:]   # [{role: user, content: ...}]
                prior_capped  = prior_messages[-20:]
                state["messages"] = prior_capped + current_input

            # Union-merge symptoms from session into current state
            saved_symptoms = saved_state.get("symptoms", []) or []
            current_symptoms = state.get("symptoms", []) or []
            state["symptoms"] = list(set(saved_symptoms) | set(current_symptoms))
            state["last_symptoms"] = saved_symptoms  # keep prior symptoms for context_synthesizer

            # Restore cross-turn context fields
            if saved_state.get("risk_level"):
                state["last_risk_level"] = saved_state["risk_level"]
            if saved_state.get("intent"):
                state["last_intent"] = saved_state["intent"]
            if saved_state.get("last_structured_summary"):
                state["last_structured_summary"] = saved_state["last_structured_summary"]
            if saved_state.get("disease_candidates"):
                state["disease_candidates"] = saved_state["disease_candidates"]

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
    log_event(logger, "history_skipped", reason="no_session_id_and_use_history_not_set")
    return state
