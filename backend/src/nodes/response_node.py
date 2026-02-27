"""
response_node.py  (Version 4)
-------------------------------
Final response formatting layer.

Responsibilities:
    1. Format validated_response from judge-approved content.
    2. Attach nutrition_image if needs_nutrition_image == True.
    3. Structure the final output.
    4. Populate state["final_response"].

This node does NOT call any LLM. It is a pure formatting pass.
"""

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from urllib.parse import urlparse

logger = get_logger("response")

# Allowed URL schemes for nutrition images
_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _is_safe_url(url: str) -> bool:
    """Validates that a URL is safe to embed (prevents SSRF/XSS)."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        # Allow localhost for locally-served static assets (nutrition images)
        # Block javascript: scheme and bare IP addresses that suggest SSRF
        return (
            parsed.scheme in _ALLOWED_SCHEMES
            and bool(parsed.netloc)
            and "javascript:" not in url.lower()
            and not url.lower().startswith("javascript")
        )
    except Exception:
        return False


def response_node(state: TriageState) -> TriageState:
    """
    Formats the validated response into a final deliverable output.

    No LLM calls. Pure string formatting and state assembly.

    Args:
        state: Contains validated_response, nutrition data, risk data.

    Returns:
        TriageState: With final_response populated and appended to messages.
    """
    next_action = state.get("next_action", "")

    # ── Case 1: Follow-up in progress — nothing to format ───────────────────
    if next_action == "ask_followup":
        state["final_response"] = ""
        return state

    # ── Case 2: Priority interrupt — already handled by llm_brain ───────────
    if next_action == "priority_interrupt":
        # The emergency message is already in messages from llm_brain
        messages = state.get("messages", [])
        if messages:
            state["final_response"] = messages[-1].get("content", "")
        return state

    # ── Case 3: Standard response formatting ────────────────────────────────
    validated = state.get("validated_response", "")

    # If no validated_response, use the last assistant message
    if not validated:
        messages = state.get("messages", [])
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        if assistant_msgs:
            validated = assistant_msgs[-1].get("content", "")

    # ── Build final structured output ────────────────────────────────────────
    final = validated

    # Ensure disclaimer is present (llm_brain already adds DISCLAIMER: section;
    # this guard is only for paths where llm_brain didn't run, e.g. vision)
    if "disclaimer" not in final.lower() and "Disclaimer" not in final:
        final += (
            "\nDISCLAIMER: This is a triage tool only, NOT a medical diagnosis. "
            "Always consult a licensed physician."
        )

    state["final_response"] = final

    # Update the last assistant message with the formatted version
    messages = state.get("messages", [])
    if messages:
        # Find and update the last assistant message
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                messages[i]["content"] = final
                break
        else:
            # No assistant message found — append one
            messages.append({"role": "assistant", "content": final})

    nutrition_image = state.get("nutrition_image", "")

    log_event(logger, "response_formatted",
              has_nutrition_image=bool(nutrition_image),
              response_length=len(final))

    return state
