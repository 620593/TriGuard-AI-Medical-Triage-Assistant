"""
save_history_node.py  (Version 3)
-----------------------------------
Last node in the graph. Persists the final state to history.json.

V2.1 change — Message cap:
    Conversation history is capped at MAX_HISTORY_MESSAGES before writing
    to disk. Only the most recent messages are kept. This prevents history.json
    from growing unboundedly across sessions and keeps disk I/O fast.

V3 change — Hardened binary / non-serialisable field stripping:
    Explicitly strips ALL fields that cannot be serialised to JSON:
      - image_input / audio_input  : raw bytes from upload handlers
      - image_type_hint            : in-memory routing hint, not needed across sessions
      - _mid_session               : internal flag; meaningless across server restarts
      - force_accepted             : transient judge retry flag
      - regeneration_count         : transient retry counter; reset each turn
      - vision_findings            : may contain complex objects; re-derived each turn
    history_tool.save_history() also has a safety net, but stripping here
    keeps the persisted schema clean and predictable.

Input:
    state (TriageState): Fully updated state from all nodes.

Returns:
    TriageState: Unchanged (pass-through — side-effect is disk write only).
"""

from backend.src.tools.history_tool import save_history
from backend.src.state.state import TriageState

# Maximum messages stored on disk across sessions.
# A session with 3 follow-ups produces at most ~8 messages (user + assistant × 4).
# 50 messages = ~6–7 full sessions of context.
MAX_HISTORY_MESSAGES = 50

# Fields that must never be written to disk.
# Bytes cannot be JSON-serialised; transient flags are meaningless after restart;
# vision_findings may contain complex objects and is re-derived on every turn.
_STRIP_FIELDS = frozenset({
    "image_input",        # raw bytes from upload handler
    "audio_input",        # raw bytes from voice handler
    "image_type_hint",    # in-memory routing hint
    "_mid_session",       # internal follow-up re-entry flag
    "force_accepted",     # transient judge retry flag
    "regeneration_count", # resets to 0 each new turn
    "vision_findings",    # may contain complex objects; re-derived each turn
})


def save_history_node(state: TriageState) -> TriageState:
    """
    Saves the current state to history.json with a rolling message window.

    Why the cap:
        Without a cap, history.json grows indefinitely across sessions.
        At 50 messages it stays tiny (<50 KB) while still giving LLaMA
        meaningful cross-session context.

    Args:
        state (TriageState): The fully updated state after all nodes have run.

    Returns:
        TriageState: Unchanged in memory (file write is the only side-effect).
    """
    # Work on a shallow copy so in-memory state is never mutated by the cap
    payload = dict(state)

    # Apply rolling window: keep only the most recent N messages for disk
    if len(payload.get("messages", [])) > MAX_HISTORY_MESSAGES:
        payload["messages"] = payload["messages"][-MAX_HISTORY_MESSAGES:]

    # Strip all non-serialisable and transient fields
    for field in _STRIP_FIELDS:
        payload.pop(field, None)

    save_history(payload)
    return state   # Return original (uncapped) state so next nodes see all messages
