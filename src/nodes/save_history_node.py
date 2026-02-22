"""
save_history_node.py  (Version 2)
-----------------------------------
Last node in the graph. Persists the final state to history.json.

V2.1 change — Message cap:
    Conversation history is capped at MAX_HISTORY_MESSAGES before writing
    to disk. Only the most recent messages are kept. This prevents history.json
    from growing unboundedly across sessions and keeps disk I/O fast.

Input:
    state (TriageState): Fully updated state from all nodes.

Returns:
    TriageState: Unchanged (pass-through — side-effect is disk write only).
"""

from src.tools.history_tool import save_history
from src.state.state import TriageState

# Maximum messages stored on disk across sessions.
# A session with 3 follow-ups produces at most ~8 messages (user + assistant × 4).
# 50 messages = ~6–7 full sessions of context.
MAX_HISTORY_MESSAGES = 50


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

    save_history(payload)
    return state   # Return original (uncapped) state so next nodes see all messages
