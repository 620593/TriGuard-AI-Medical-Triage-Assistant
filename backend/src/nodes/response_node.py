"""
response_node.py  (Version 6 — UX Rewrite)
--------------------------------------------
Deterministic, warm-toned presentation orchestration node.

V6 contract:
    - Input:  state["llm_output"] (structured dict from llm_brain)
    - Output: state["formatted_response"] + state["final_response"]
    - No LLM calls. Pure orchestration.
    - All string formatting delegated to presentation_formatter module.
    - Tone is deterministic based on urgency.
    - Nutrition text section appended immediately (image generated async later).
    - Disclaimer always appended (short, not loud).
    - Observability trace written to state["system_trace"].
"""

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from backend.src.tools.presentation_formatter import (
    apply_tone,
    format_nutrition_section,
)

logger = get_logger("response")

_DISCLAIMER = (
    "\n\n⚠️ Disclaimer: TriGuard is a triage support tool — not a substitute "
    "for a licensed physician. Always consult a qualified healthcare professional "
    "for personal medical advice."
)


# ── Private state helpers ─────────────────────────────────────────────────────

def _update_message_history(state: TriageState, formatted: str) -> list:
    """
    Returns a new messages list with the last assistant message updated.
    Does not mutate state directly — caller sets state["messages"].
    """
    messages = list(state.get("messages") or [])
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant":
            messages[i] = {**messages[i], "content": formatted}
            return messages
    messages.append({"role": "assistant", "content": formatted})
    return messages


def _build_system_trace(state: TriageState, next_action: str) -> dict:
    """Constructs the observability trace dict from final state values."""
    return {
        "intent":                    state.get("intent", ""),
        "risk_level":                state.get("risk_level", ""),
        "urgency":                   state.get("urgency", "routine"),
        "red_flag_triggered":        state.get("red_flag_triggered", False),
        "emergency_call_triggered":  state.get("emergency_call_triggered", False),
        "followup":                  next_action == "ask_followup",
        "fallback_used":             state.get("fallback_used", False),
        "nutrition_image_required":  state.get("nutrition_image_required", False),
    }


# ── Node ──────────────────────────────────────────────────────────────────────

def response_node(state: TriageState) -> TriageState:
    """
    Orchestrates the final user-facing response assembly.

    No LLM calls. No string formatting logic — delegates completely to
    presentation_formatter. Handles three execution paths, appends disclaimer,
    updates message history, and writes observability trace.

    Args:
        state: Contains llm_output, urgency, nutrition data.

    Returns:
        TriageState: formatted_response, final_response, system_trace populated.
    """
    next_action = state.get("next_action", "")

    # ── Case 1: Follow-up in progress ────────────────────────────────────────
    if next_action == "ask_followup":
        state["formatted_response"] = ""
        state["final_response"]     = ""
        state["system_trace"]       = _build_system_trace(state, next_action)
        return state

    # ── Case 2: Emergency interrupt (handled by llm_brain fast-exit) ─────────
    if next_action == "priority_interrupt":
        messages = state.get("messages", [])
        last_msg = messages[-1].get("content", "") if messages else ""
        state["formatted_response"] = last_msg
        state["final_response"]     = last_msg
        state["system_trace"]       = _build_system_trace(state, next_action)
        return state

    # ── Case 3: Standard response formatting ─────────────────────────────────
    llm_output = state.get("llm_output", {})
    urgency    = state.get("urgency", "routine")

    # Pass vision_findings for body_image cases to get the detailed image section
    vision_findings = (
        state.get("vision_findings")
        if state.get("intent") == "body_image"
        else None
    )

    # If llm_output is empty (vision fallback path), pull from last message
    if not llm_output:
        messages  = state.get("messages", [])
        asst_msgs = [m for m in messages if m.get("role") == "assistant"]
        fallback  = asst_msgs[-1].get("content", "") if asst_msgs else ""
        state["formatted_response"] = fallback + _DISCLAIMER
        state["final_response"]     = state["formatted_response"]
    else:
        formatted = apply_tone(llm_output, urgency, vision_findings=vision_findings)

        # ── Simple English response post-processing ──────────────────────────
        JARGON_MAP = {
            "viral infection": "infection caused by a virus",
            "bacterial infection": "infection caused by bacteria",
            "inflammation": "swelling and irritation",
            "consult a physician": "see a doctor",
            "administer": "take",
            "symptoms indicate": "your symptoms suggest",
            "clinical presentation": "how you are feeling",
            "differential diagnosis": "possible causes",
            "recommended course of action": "what you should do",
        }
        for old, new in JARGON_MAP.items():
            formatted = formatted.replace(old, new)
            formatted = formatted.replace(old.capitalize(), new.capitalize())

        # ── Append OTC suggestions if present ────────────────────────────────
        suggested_otc = llm_output.get("suggested_otc")
        if suggested_otc:
            otc_block = (
                f"\n\n💊 OTC Suggestion (as you asked):\n{suggested_otc}\n"
                "⚠️ Warning: These are over-the-counter medicines available without "
                "prescription. Take as per package instructions. Do NOT take if you "
                "are pregnant, have kidney/liver disease, or are already on other "
                "medications without consulting a doctor first. If symptoms worsen "
                "after 2 days, see a doctor immediately."
            )
            formatted += otc_block

        # ── Append Nutrition Tip if present ──────────────────────────────────
        nutrition_tip = llm_output.get("nutrition_tip")
        if nutrition_tip:
            formatted += f"\n\n🥗 Nutrition Tip: {nutrition_tip}"

        # Append nutrition section immediately (image generated async after this
        # node returns — see async_nutrition_image_node in the graph)
        nutrition_section = format_nutrition_section(state.get("nutrition_output"))
        if nutrition_section:
            formatted += nutrition_section
            # Signal async_nutrition_image_node to fire in the next graph step
            state["nutrition_image_required"] = True

        formatted += _DISCLAIMER

        state["formatted_response"] = formatted
        state["final_response"]     = formatted
        state["messages"]           = _update_message_history(state, formatted)

    # ── Write observability trace ─────────────────────────────────────────────
    state["system_trace"] = _build_system_trace(state, next_action)

    log_event(logger, "response_formatted",
              urgency=urgency,
              risk_level=state.get("risk_level", ""),
              response_length=len(state.get("formatted_response", "")))
    return state
