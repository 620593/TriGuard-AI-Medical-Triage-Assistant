"""
save_history_node.py  (Version 4 — Clean Message Pairs)
--------------------------------------------------------
Last node in the graph. Persists the final state to history.json.

V4 Changes (over V3):
    - Ensures both the user turn AND assistant response are included in
      the messages list before writing. Prior versions relied on messages
      being accumulated by earlier nodes; this version defensively patches
      in the current turn's pair if they are missing.
    - Writes user_input + final_response as a clean message pair when the
      assistant response is not already the last message in state["messages"].
    - Rolling window preserved at 50 messages.
    - Strip logic unchanged.
"""

from backend.src.tools.history_tool import save_history
from backend.src.state.state import TriageState

# Maximum messages stored on disk across sessions.
MAX_HISTORY_MESSAGES = 50

_STRIP_FIELDS = frozenset({
    "image_input",
    "audio_input",
    "image_type_hint",
    "_mid_session",
    "force_accepted",
    "regeneration_count",
    "vision_findings",
    "session_memory",    # transient — rebuilt each turn
    "new_session",       # transient flag
})


def save_history_node(state: TriageState) -> TriageState:
    """
    Saves the current turn to history.json with a rolling message window.

    Ensures the assistant response is recorded even if it was written to
    state["final_response"] rather than appended to state["messages"].
    """
    payload = dict(state)

    # ── Ensure both user+assistant messages are in the list ──────────────────
    messages = list(payload.get("messages", []))
    user_input    = (state.get("user_input") or "").strip()
    final_response = (state.get("final_response") or "").strip()

    # If the last message is not the assistant's response, append it
    last_is_assistant = (
        messages and messages[-1].get("role") == "assistant"
    )
    if not last_is_assistant and final_response:
        if user_input:
            # Also add the user message if not already present
            second_last_is_user = (
                len(messages) >= 1 and messages[-1].get("role") == "user"
            )
            if not second_last_is_user:
                messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": final_response})

    # Apply rolling window: keep only the most recent N messages for disk
    payload["messages"] = messages[-MAX_HISTORY_MESSAGES:]

    # Strip all non-serialisable and transient fields
    for field in _STRIP_FIELDS:
        payload.pop(field, None)

    save_history(payload)
    return state  # Return original (uncapped) state so next nodes see all messages
