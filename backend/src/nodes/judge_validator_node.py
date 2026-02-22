"""
judge_validator_node.py  (Version 3 — NEW)
--------------------------------------------
Second-pass LLM that validates the primary LLaMA response against:
    1. Retrieved Tavily information (grounding check).
    2. Risk evaluation output (consistency check).
    3. Anti-hallucination policy (no invented diseases, no prescriptions).

If hallucination is detected:
    → Regenerates the response using only grounded information.
    → Logs the incident for observability.

This node runs AFTER llm_brain_node and BEFORE save_session_node.
"""

from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from backend.src.tools.mongodb_tool import insert_log

logger = get_logger("judge_validator")

# Maximum regeneration attempts before accepting the response
MAX_RETRIES = 2


def judge_validator_node(state: TriageState) -> TriageState:
    """
    Validates the current assistant response for hallucination and consistency.

    Args:
        state: Contains messages, retrieved_info, risk_level, risk_score.

    Returns:
        TriageState: Updated with judge_passed flag and potentially regenerated response.
    """
    messages = state.get("messages", [])
    retrieved_info = state.get("retrieved_info", [])
    risk_level = state.get("risk_level", "")
    risk_score = state.get("risk_score", 0.0)

    # Skip validation for follow-up questions and priority interrupts
    next_action = state.get("next_action", "")
    if next_action in ("ask_followup", "priority_interrupt"):
        state["judge_passed"] = True
        state["judge_feedback"] = ""
        return state

    # Get the latest assistant response to validate
    assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
    if not assistant_msgs:
        state["judge_passed"] = True
        state["judge_feedback"] = ""
        return state

    current_response = assistant_msgs[-1]["content"]
    context_snippet = " | ".join(retrieved_info)[:400] if retrieved_info else "None"

    # ── Validation prompt ──────────────────────────────────────────────────────
    judge_prompt = (
        "You are a STRICT medical triage quality validator.\n\n"
        "Check if the RESPONSE violates ANY of these rules:\n"
        "1. Mentions disease names NOT found in the CONTEXT.\n"
        "2. Prescribes specific medication or dosage.\n"
        "3. Gives a definitive diagnosis (e.g., 'You have X').\n"
        "4. Risk level in response contradicts the ASSESSED RISK.\n"
        "5. Invents symptoms the patient did NOT report.\n\n"
        f"CONTEXT (from medical search): {context_snippet}\n"
        f"ASSESSED RISK: {risk_level} ({risk_score}/10)\n"
        f"RESPONSE TO VALIDATE:\n{current_response}\n\n"
        "If the response is safe and accurate, reply: PASS\n"
        "If it violates any rule, reply: FAIL — [brief reason]\n\n"
        "Verdict:"
    )

    verdict = call_llama(judge_prompt, max_tokens=60).strip()

    if verdict.upper().startswith("PASS"):
        state["judge_passed"] = True
        state["judge_feedback"] = ""
        log_event(logger, "judge_validated", result="pass")
        return state

    # ── Hallucination detected — attempt regeneration ─────────────────────────
    state["judge_feedback"] = verdict
    log_event(logger, "hallucination_detected",
              feedback=verdict,
              escalation_flag=True)

    # Regenerate a safer response using only grounded information
    symptom_str = ", ".join(state.get("symptoms", []))
    regen_prompt = (
        "You are TriGuard AI, a medical triage assistant.\n"
        "A previous response was flagged for potential inaccuracy.\n"
        "Generate a NEW response using ONLY the information below.\n"
        "Do NOT diagnose. Do NOT prescribe. Do NOT invent disease names.\n\n"
        f"Patient symptoms: {symptom_str}\n"
        f"Medical context: {context_snippet}\n"
        f"Risk level: {risk_level.upper()} ({risk_score:.1f}/10)\n\n"
        "Use this format:\n"
        "🩺 Summary: [1-2 lines]\n"
        f"📊 Risk Level: {risk_level.upper()} ({risk_score:.1f}/10)\n"
        "💡 Suggested Action: [what to do]\n"
        "⚠️ When To Seek Immediate Help: [red flags]\n\n"
        "Write the response:"
    )

    regenerated = call_llama(regen_prompt, max_tokens=350).strip()

    if regenerated:
        regenerated += (
            "\n\n⚠️ Disclaimer: This is a triage tool only, NOT a medical diagnosis. "
            "Always consult a licensed physician."
        )
        # Replace the last assistant message with the regenerated one
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant":
                messages[i]["content"] = regenerated
                break

        state["judge_passed"] = True
        state["judge_feedback"] = f"Regenerated. Original issue: {verdict}"
        log_event(logger, "response_regenerated", reason=verdict)
    else:
        # Could not regenerate — mark as failed but don't block
        state["judge_passed"] = False
        log_event(logger, "regeneration_failed", reason=verdict)

    return state
