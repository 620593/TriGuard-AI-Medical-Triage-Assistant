"""
context_synthesizer_node.py  (Version 8 — Full In-Session Memory)
------------------------------------------------------------------
Merges prior findings, SESSION MEMORY, and current query into reasoning_input.

V8 Changes (over V7):
    - SESSION MEMORY block: Built from state["messages"] (last 10 turns).
      This block is injected at the TOP of reasoning_input so llm_brain
      always has full conversation context for follow-up questions.
      Format:
          === SESSION MEMORY (current chat) ===
          [User]: <message>
          [TriGuard]: <response>
          ... (last 10 turns)
          === END SESSION MEMORY ===
    - Accumulated symptoms are taken from UNION of current + last_symptoms.
    - last_risk_level and disease_candidates from prior turns are preserved
      and forwarded into the enrichment block even when not re-detected.
    - 600-char summary cap replaced by SESSION MEMORY when messages exist.

V7 rules (preserved):
    - No LLM usage.
    - No routing logic.
    - Pure string assembly.
    - Output: state["reasoning_input"]
"""

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("context_synthesizer")

_MAX_SUMMARY_CHARS   = 600
_MAX_EXTRACTED_CHARS = 800
_MAX_RETRIEVED_CHARS = 600
_SESSION_MEMORY_TURNS = 10   # last N user+assistant pairs to include


def _build_session_memory_block(messages: list) -> str:
    """
    Formats the last _SESSION_MEMORY_TURNS × 2 messages (user+assistant pairs)
    into a clean SESSION MEMORY block for the LLM prompt.

    Returns empty string when there are ≤1 messages (no prior context yet).
    """
    # Filter to only user/assistant messages (exclude system messages)
    convo = [m for m in messages if m.get("role") in ("user", "assistant")]

    # We need at least one prior exchange (2 messages: user + assistant)
    # The LAST message is always the current user turn — skip it
    prior = convo[:-1] if convo else []
    if not prior:
        return ""

    # Take last N turns worth of messages
    window = prior[-(  _SESSION_MEMORY_TURNS * 2):]

    lines = ["=== SESSION MEMORY (current chat) ==="]
    for msg in window:
        role = msg.get("role", "")
        content = (msg.get("content", "") or "").strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"[User]: {content}")
        elif role == "assistant":
            # Truncate very long assistant messages to keep prompt size manageable
            lines.append(f"[TriGuard]: {content[:600]}" + ("…" if len(content) > 600 else ""))
    lines.append("=== END SESSION MEMORY ===")

    # Only return the block if we actually have conversation lines
    return "\n".join(lines) if len(lines) > 2 else ""


def context_synthesizer_node(state: TriageState) -> TriageState:
    """
    Assembles reasoning_input from all available context sources.

    V8 Priority order:
        0. SESSION MEMORY block (last 10 turns — ALWAYS first)
        1. last_structured_summary (prior image/xray/text findings, 600-char cap)
        2. Vision findings block (body_image intent only)
        3. OCR extracted text (medical_report intent)
        4. Extracted symptoms + disease candidates + Tavily evidence (medical_text)
        5. Current risk assessment (score, level, red flags)
        6. User input (current text query)
    """
    intent         = state.get("intent", "medical_text")
    user_input     = (state.get("user_input", "") or "").strip()
    prior_summary  = (state.get("last_structured_summary", "") or "").strip()
    extracted_text = (state.get("extracted_text", "") or "").strip()
    prior_risk     = (state.get("last_risk_level", "") or "").strip()
    prior_intent   = (state.get("last_intent", "") or "").strip()
    messages       = state.get("messages", []) or []

    # Truncate long inputs to control prompt size
    prior_summary  = prior_summary[:_MAX_SUMMARY_CHARS]
    extracted_text = extracted_text[:_MAX_EXTRACTED_CHARS]

    has_ocr     = bool(extracted_text)

    parts: list[str] = []

    # ── 0. SESSION MEMORY block (top priority — always prepended) ────────────
    # Built from state["messages"] which load_history_node already populated
    # with the prior saved messages + current user turn.
    session_memory_block = _build_session_memory_block(messages)
    if session_memory_block:
        parts.append(session_memory_block)
        # Cache to state for observability
        state["session_memory"] = session_memory_block

    # ── 0.5 PRIOR HISTORY block (Cross-Session Memory) ───────────────────────
    prior_history_context = state.get("prior_history_context", "").strip()
    if prior_history_context:
        parts.append(prior_history_context)

    # ── 1. Prior turn summary (fallback when no session memory yet) ──────────
    # Only add the PRIOR ANALYSIS block if there's no richer session memory
    is_followup = bool(prior_summary and user_input and not session_memory_block)
    if is_followup:
        prior_block = (
            f"[PRIOR ANALYSIS ({prior_intent.upper() if prior_intent else 'PREVIOUS TURN'})]\n"
            f"Risk Level: {prior_risk.upper() if prior_risk else 'UNKNOWN'}\n"
            f"Findings: {prior_summary}"
        )
        parts.append(prior_block)

    # ── 2. Vision findings (body_image intent only) ───────────────────────────
    if intent == "body_image" and state.get("vision_findings"):
        vf = state["vision_findings"]

        image_type_vf      = vf.get("image_type", "unknown")
        visual_findings    = vf.get("visual_findings", [])
        lesion_morphology  = vf.get("lesion_morphology") or ""
        color_description  = vf.get("color_description") or ""
        distribution       = vf.get("distribution") or ""
        severity           = vf.get("severity") or ""
        possible_cond      = vf.get("possible_conditions", [])
        explanation        = vf.get("explanation", "")
        confidence         = vf.get("confidence", 0.0)

        vision_lines = [
            f"[VISUAL ANALYSIS — {image_type_vf.upper()} IMAGE]",
            f"Confidence: {confidence:.0%}",
        ]
        if visual_findings:
            vision_lines.append("Visual findings:")
            for f_item in visual_findings[:6]:
                vision_lines.append(f"  • {f_item}")
        if lesion_morphology:
            vision_lines.append(f"Lesion morphology: {lesion_morphology}")
        if color_description:
            vision_lines.append(f"Color: {color_description}")
        if distribution:
            vision_lines.append(f"Distribution: {distribution}")
        if severity:
            vision_lines.append(f"Severity: {severity}")
        if possible_cond:
            vision_lines.append(
                "Possible conditions (differential): "
                + ", ".join(str(c) for c in possible_cond[:5])
            )
        if explanation:
            vision_lines.append(f"\nAI Explanation:\n{explanation}")
        vision_lines.append(f"\nRisk level (pre-LLM assessment): {state.get('risk_level', 'unknown').upper()}")

        parts.append("\n".join(vision_lines))

    # ── 3. OCR document text ──────────────────────────────────────────────────
    if has_ocr:
        parts.append(f"[DOCUMENT TEXT (OCR)]\n{extracted_text}")

    # ── 4. Medical enrichment block (medical_text & casual intents) ───────────
    if intent in ("medical_text", "casual"):
        # Merge current-turn symptoms with accumulated symptoms from prior turns
        current_symptoms   = state.get("symptoms", []) or []
        last_symptoms      = state.get("last_symptoms", []) or []
        all_symptoms       = list(dict.fromkeys(current_symptoms + last_symptoms))  # ordered dedup

        disease_candidates = state.get("disease_candidates", []) or []
        retrieved_info     = state.get("retrieved_info", []) or []
        risk_score         = state.get("risk_score", 0.0)
        risk_level         = state.get("risk_level", "") or state.get("last_risk_level", "unknown")
        red_flag           = state.get("red_flag_triggered", False)

        enrichment_lines: list[str] = []

        if all_symptoms:
            enrichment_lines.append(
                "Reported symptoms (this session): " + ", ".join(str(s) for s in all_symptoms[:15])
            )

        if disease_candidates:
            enrichment_lines.append(
                "Possible conditions (differential): "
                + ", ".join(str(d) for d in disease_candidates[:6])
            )

        if retrieved_info:
            combined = " | ".join(str(r) for r in retrieved_info[:5])
            enrichment_lines.append(
                f"Medical evidence (retrieved):\n{combined[:_MAX_RETRIEVED_CHARS]}"
            )

        if risk_level:
            enrichment_lines.append(
                f"Risk assessment: {risk_level.upper()} "
                f"(score: {risk_score:.1f}/10)"
                + (" | ⚠️ RED FLAG TRIGGERED" if red_flag else "")
            )

        if enrichment_lines:
            parts.append("[CLINICAL CONTEXT]\n" + "\n".join(enrichment_lines))

    # ── 5. User input ─────────────────────────────────────────────────────────
    if user_input:
        if intent == "body_image":
            parts.append(f"User question:\n{user_input}")
        else:
            # If session memory is present, every follow-up is a FOLLOW-UP QUESTION
            label = "FOLLOW-UP QUESTION" if (is_followup or session_memory_block) else "PATIENT INPUT"
            parts.append(f"[{label}]\n{user_input}")

    reasoning_input = "\n\n".join(parts).strip()

    # Absolute fallback
    if not reasoning_input:
        reasoning_input = extracted_text or user_input or "No patient input provided."

    state["reasoning_input"] = reasoning_input

    log_event(logger, "context_synthesized",
              has_session_memory=bool(session_memory_block),
              is_followup=is_followup,
              has_ocr=has_ocr,
              intent=intent,
              symptoms_count=len(state.get("symptoms", []) or []),
              retrieved_count=len(state.get("retrieved_info", []) or []),
              reasoning_length=len(reasoning_input))
    return state
