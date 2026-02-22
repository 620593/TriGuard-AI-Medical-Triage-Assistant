"""
load_history_node.py  (Version 2 — Session Manager)
------------------------------------------------------
First node in the graph. Manages session state from history.json.

Three behaviours:
  1. new_session  → Wipe old history; start clean. (python -m src.main --new)
  2. _mid_session → Already in a follow-up loop; state is correct in memory.
                    Skip disk read to prevent message duplication.
  3. first turn   → Load history.json and merge prior context into state.

Why the _mid_session flag (not followup_count):
    followup_count is managed internally by followup_node, not by main.py.
    Relying on it here would couple two unrelated concerns.
    _mid_session is an explicit, intent-expressing flag set by main.py
    ONLY when it is about to re-invoke the graph for a follow-up turn.
    This removes tight coupling and makes the guard testable in isolation.

Input:
    state (TriageState): State from main.py (fresh, mid-session, or new-session).

Returns:
    TriageState: State ready for the rest of the pipeline.
"""

from backend.src.tools.history_tool import load_history
from backend.src.state.state import TriageState


def load_history_node(state: TriageState) -> TriageState:
    """
    Loads, resets, or passes through session state depending on context.

    Args:
        state (TriageState): State built by main.py or carried from a prior turn.

    Returns:
        TriageState: State ready for symptom extraction and further processing.
    """
    # ── Branch 1: New session requested ───────────────────────────────────────
    # User ran: python -m src.main --new
    # Wipe everything except the current user message and start fresh.
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
        return state

    # ── Branch 2: Mid-session follow-up loop ───────────────────────────────────
    # main.py sets _mid_session=True before each follow-up re-invocation.
    # State is already correctly populated in memory — skip disk to avoid
    # prepending history messages a second time (which would double them).
    if state.get("_mid_session", False):
        return state   # State is already correct — no disk read needed

    # ── Branch 3: First turn of a continuing session ──────────────────────────
    # Load history.json and merge prior context (cross-session continuity).
    history = load_history()   # Returns {} if file doesn't exist

    if history:
        # Prepend prior messages so LLaMA has conversation context
        if history.get("messages"):
            state["messages"] = history["messages"] + state["messages"]

        # Restore follow-up count from prior turn
        state["followup_count"] = history.get("followup_count", 0)

        # Merge previously identified symptoms (union — no duplicates)
        if history.get("symptoms"):
            existing = set(history["symptoms"])
            current = set(state.get("symptoms", []))
            state["symptoms"] = list(existing | current)

    return state
