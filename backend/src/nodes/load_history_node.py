"""
load_history_node.py  (Version 3 — History Opt-In)
------------------------------------------------------
Manages session state from history.json.

V3 changes:
    - History loading is now OPT-IN via state['use_history'].
    - By default (use_history is absent or False), the node is a pure
      pass-through. Each request starts with a clean, isolated context.
    - Only when the user explicitly requests past history
      (use_history=True in the API call) are prior messages merged.
    - Fewer tokens in context = faster LLM inference.

Three behaviours:
  1. use_history=False (default) → Pass-through. No disk read.
  2. new_session                 → Wipe state fields; start clean.
  3. use_history=True            → Load history.json and merge (capped at 10 msgs).
"""

from backend.src.tools.history_tool import load_history
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("load_history")


def load_history_node(state: TriageState) -> TriageState:
    """
    Loads, resets, or passes through session state depending on context.

    Args:
        state (TriageState): State built by the API endpoint.

    Returns:
        TriageState: State ready for the rest of the pipeline.
    """
    # ── Branch 1: New session requested ──────────────────────────────────────────
    if state.get("next_action") == "new_session":
        state["next_action"] = ""
        state["followup_count"] = 0
        state["symptoms"] = []
        state["retrieved_info"] = []
        state["risk_score"] = 0.0
        state["risk_level"] = ""
        state["risk_confidence"] = 0.0
        state["mental_health_flag"] = False
        state["messages"] = [state["messages"][-1]]   # Keep only current input
        log_event(logger, "history_reset", reason="new_session")
        return state

    # ── Branch 2: Mid-session follow-up loop ────────────────────────────────────
    # State is already correct in memory. Skip to avoid double-prepending.
    if state.get("_mid_session", False):
        return state

    # ── Branch 3: History opt-in check (DEFAULT: skip) ────────────────────────
    # History is NOT loaded unless the caller explicitly sets use_history=True.
    # This keeps each triage request isolated with a clean LLM context window,
    # improves inference speed, and prevents cross-session hallucinations.
    if not state.get("use_history", False):
        log_event(logger, "history_skipped", reason="use_history_not_set")
        return state

    # ── Branch 4: Explicit history load (opt-in) ──────────────────────────────
    history = load_history()

    if history:
        if history.get("messages"):
            # Cap merged history at 10 messages to keep context lean
            recent_history = history["messages"][-10:]
            state["messages"] = recent_history + state["messages"]

        state["followup_count"] = history.get("followup_count", 0)

        if history.get("symptoms"):
            existing = set(history["symptoms"])
            current = set(state.get("symptoms", []))
            state["symptoms"] = list(existing | current)

        log_event(logger, "history_loaded",
                  message_count=len(history.get("messages", [])),
                  symptom_count=len(history.get("symptoms", [])))

    return state
