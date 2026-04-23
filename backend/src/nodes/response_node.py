"""
rresponse_node.py  (Version 8 — Vision-Aware Section Format)
--------------------------------------------------------------
V8 changes:
  - Dedicated xray formatting path: uses state["xray_findings"] directly.
    Does NOT use build_response() for xray — avoids "Symptoms: None" confusion.
    Produces clean ### sections: X-Ray Review, Actions, When to See a Doctor.
  - Dedicated body_image formatting path: uses state["vision_findings"] directly.
    Builds ### sections: Skin Analysis, Possible Conditions, Recommended Actions, When to See a Doctor.
  - Standard 7-section format unchanged for medical_text / medical_report.
  - Casual/mental health short-circuit unchanged.
  - X-ray fracture urgency: confidence>0.7 on non-normal finding → urgent doctor advice.

V7 contract (preserved):
  - No external LLM calls.
  - All string logic self-contained or delegated to formatter.
  - Observability trace written to state["system_trace"].
"""

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from backend.src.services.response_formatter import build_response

logger = get_logger("response")

_CALM_REPLACEMENTS = {
    "MUST consult": "should consult",
    "must consult": "should consult",
    "must be reviewed": "should be reviewed",
    "seek immediate emergency care": "please go to the nearest emergency room",
    "Seek immediate emergency care": "Please go to the nearest emergency room",
    "These findings MUST be reviewed": "It's a good idea to have this reviewed",
    "⚠️ IMPORTANT:": "",
    "IMPORTANT:": "",
}


def _apply_calm_tone(text: str, risk_level: str) -> str:
    """Strips alarming language."""
    if not text:
        return ""
    cleaned = text
    for old, new in _CALM_REPLACEMENTS.items():
        cleaned = cleaned.replace(old, new)
    return cleaned.rstrip()


def _update_message_history(state: TriageState, formatted: str) -> list:
    """Updates the last assistant message in the conversation history."""
    messages = list(state.get("messages") or [])
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant":
            messages[i] = {**messages[i], "content": formatted}
            return messages
    messages.append({"role": "assistant", "content": formatted})
    return messages


def _build_system_trace(state: TriageState, next_action: str) -> dict:
    return {
        "intent":                   state.get("intent", ""),
        "risk_level":               state.get("risk_level", ""),
        "urgency":                  state.get("urgency", "routine"),
        "red_flag_triggered":       state.get("red_flag_triggered", False),
        "emergency_call_triggered": state.get("emergency_call_triggered", False),
        "followup":                 next_action == "ask_followup",
        "fallback_used":            state.get("fallback_used", False),
        "nutrition_image_required": state.get("nutrition_image_required", False),
    }


# ── X-Ray dedicated formatter ──────────────────────────────────────────────────

def _build_xray_response(state: TriageState) -> str:
    """
    Builds a clean 3-section response for X-ray analysis using xray_findings.
    Does NOT use build_response() to avoid the Symptoms/Conditions mismatch.
    """
    xray_findings = state.get("xray_findings", "")
    risk_level    = state.get("risk_level", "low").lower()
    vision        = state.get("vision_findings", {})

    # Extract body part and labels from vision_findings if available
    body_region   = vision.get("body_region", "the area in the X-ray")

    # Clean up xray_findings text (remove embedded ### if present — we rebuild structure)
    # Strip any leading section header so we don't double-wrap
    explanation = xray_findings
    if "### 🩻" in explanation:
        # Extract just the body text after the header
        parts = explanation.split("\n\n", 1)
        explanation = parts[1].strip() if len(parts) > 1 else explanation
    # Strip trailing disclaimer — UI handles it
    explanation = explanation.replace(
        "---\n\n*TriGuard is a screening aid — not a diagnosis. Please consult a qualified doctor.*",
        ""
    ).strip()

    # Determine urgency based on risk and confidence
    confidence   = getattr(state.get("vision_findings", {}), "get", lambda k, d: d)("confidence", 0.5)
    if isinstance(vision, dict):
        confidence = vision.get("confidence", 0.5)

    is_urgent = risk_level in ("high", "critical")
    is_fracture_likely = any(
        kw in xray_findings.lower()
        for kw in ("fracture", "break", "crack", "fractured", "broken", "distal fibula",
                   "fibula", "tibia", "bone injury", "fragment")
    )

    # ── Section 1: X-Ray Findings
    sections = [f"### 🩻 X-Ray Review\n\n{explanation}"]

    # ── Section 2: Recommended Actions
    if is_fracture_likely:
        actions = (
            "• Visit an orthopaedic doctor or emergency department as soon as possible\n"
            "• Avoid putting weight on the affected limb until evaluated\n"
            "• Apply ice wrapped in cloth to reduce swelling (20 min on / 20 min off)\n"
            "• Keep the limb elevated if possible\n"
            "• Do NOT try to realign or bandage the bone yourself"
        )
    else:
        actions = (
            "• See a doctor or radiologist for a full interpretation of this X-ray\n"
            "• Bring a copy of this image to your appointment\n"
            "• Note any pain, discomfort, or swelling to describe to your doctor"
        )

    sections.append(f"### 🧘 Recommended Actions\n\n{actions}")

    # ── Section 3: When to See a Doctor
    if is_fracture_likely:
        doctor_text = (
            "🚨 Please see a doctor **today or go to a hospital emergency department**. "
            "The X-ray shows a possible bone break that needs urgent medical attention. "
            "A doctor will confirm with further tests and decide the right treatment."
        )
    elif is_urgent:
        doctor_text = (
            "Please see a doctor **as soon as possible** — ideally within 24 hours. "
            "The findings in this X-ray need professional evaluation."
        )
    else:
        doctor_text = (
            "It's important to follow up with your doctor within the next 1–2 days "
            "to get a complete interpretation of this X-ray from a qualified radiologist."
        )

    sections.append(f"### 🚨 When to See a Doctor\n\n{doctor_text}")

    return "\n\n---\n\n".join(sections)


# ── Body/Skin Image dedicated formatter ───────────────────────────────────────

def _build_body_image_response(state: TriageState) -> str:
    """
    Builds a clean 5-section response for body/skin image analysis.
    Uses vision_findings["explanation"], ["possible_conditions"], ["severity"].
    """
    vision     = state.get("vision_findings", {}) or {}
    risk_level = state.get("risk_level", "low").lower()

    explanation        = vision.get("explanation", "")
    visual_findings    = vision.get("visual_findings", [])
    possible_conditions = vision.get("possible_conditions", [])
    severity           = vision.get("severity", "moderate")
    body_region        = vision.get("body_region", "the affected area")
    distribution       = vision.get("distribution", "")
    color_desc         = vision.get("color_description", "")
    lesion_morph       = vision.get("lesion_morphology", "")

    # If explanation is missing, build from fields
    if not explanation:
        parts = []
        if visual_findings:
            parts.append("The image shows: " + ", ".join(visual_findings[:3]) + ".")
        if color_desc:
            parts.append(f"The coloring appears {color_desc}.")
        if lesion_morph:
            parts.append(f"The texture/surface: {lesion_morph}.")
        if distribution:
            parts.append(f"Distribution: {distribution}.")
        explanation = " ".join(parts) if parts else "Image analyzed. Please consult a doctor for detailed assessment."

    confidence = float(vision.get("confidence", 0.0) or 0.0)

    # ── Section 1: What We Can See
    observation_lines = [
        f"### 👁️ What We See\n\n{explanation}",
        f"Observed area: {body_region}",
        f"Image confidence: {confidence:.0%}",
    ]

    if visual_findings:
        observation_lines.append("\nKey visible findings:")
        for finding in visual_findings[:6]:
            observation_lines.append(f"• {finding}")

    if color_desc:
        observation_lines.append(f"Color pattern: {color_desc}")
    if lesion_morph:
        observation_lines.append(f"Lesion pattern: {lesion_morph}")
    if distribution:
        observation_lines.append(f"Distribution: {distribution}")

    sections = ["\n".join(observation_lines)]

    # ── Section 2: Possible Skin Conditions
    if possible_conditions:
        cond_lines = "\n".join(f"• {c} *(possible, not confirmed)*" for c in possible_conditions[:5])
        sections.append(
            f"### 🩺 Possible Conditions\n\n"
            f"Based on what's visible, this *may suggest* one of the following — "
            f"only a doctor can confirm:\n\n{cond_lines}"
        )

    # ── Section 2.5: What To Watch For
    watch_for = (
        "• Rapid spreading of redness/rash\n"
        "• New pain, warmth, pus, or bleeding\n"
        "• Fever or feeling generally unwell\n"
        "• Swelling around eyes, lips, or breathing discomfort"
    )
    sections.append(f"### 🔎 What To Watch For\n\n{watch_for}")

    # ── Section 3: Recommended Actions
    if severity in ("severe", "high") or risk_level in ("high", "critical"):
        actions = (
            "• See a dermatologist or doctor **soon** — ideally within 24–48 hours\n"
            "• Avoid scratching or applying unknown creams to the area\n"
            "• Take a clear photo in good lighting to show your doctor\n"
            "• Note when it started and whether it is spreading"
        )
    elif severity == "moderate" or risk_level == "moderate":
        actions = (
            "• Schedule a visit to your doctor or dermatologist within a few days\n"
            "• Keep the area clean and dry\n"
            "• Avoid known irritants (harsh soaps, synthetic fabrics)\n"
            "• Consider an over-the-counter antihistamine if there is itching"
        )
    else:
        actions = (
            "• Monitor the area over the next few days for any changes\n"
            "• Keep the area clean and moisturised\n"
            "• If it spreads, blisters, or causes pain, see a doctor promptly"
        )

    sections.append(f"### 🧘 Recommended Actions\n\n{actions}")

    # ── Section 4: When to See a Doctor
    if severity in ("severe",) or risk_level in ("high", "critical"):
        doctor_text = (
            "🚨 Please see a dermatologist or doctor **as soon as possible**. "
            "The findings look significant and deserve prompt medical attention."
        )
    elif severity == "moderate" or risk_level == "moderate":
        doctor_text = (
            "We recommend seeing a doctor or dermatologist within the next 2–3 days. "
            "A proper examination is needed for an accurate diagnosis."
        )
    else:
        doctor_text = (
            "If the condition persists for more than a week or worsens, "
            "visit a dermatologist for a proper assessment."
        )

    sections.append(f"### 🚨 When to See a Doctor\n\n{doctor_text}")

    return "\n\n---\n\n".join(sections)


# ── Main Node ──────────────────────────────────────────────────────────────────

def response_node(state: TriageState) -> TriageState:
    """
    Assembles the final user-facing response.

    Routing:
      - casual_response     → mental_health_text passthrough
      - ask_followup        → already set by followup_node, skip
      - history_response    → already set by followup_node, skip
      - priority_interrupt  → emergency fast-path
      - all other intents   → 7-section format via response_formatter
        (xray and body_image arrive here via vision_bridge with state["symptoms"] set)
    """
    next_action = state.get("next_action", "")
    intent      = state.get("intent", "medical_text")

    # ── Case 1a: Casual / mental health short-circuit ──────────────────────────
    if next_action == "casual_response":
        casual_text = state.get("mental_health_text", "I'm here to help! How are you feeling?")
        state["formatted_response"] = casual_text
        state["final_response"]     = casual_text
        messages = state.get("messages", [])
        messages.append({"role": "assistant", "content": casual_text})
        state["messages"] = messages
        state["system_trace"] = _build_system_trace(state, "casual_response")
        return state

    # ── Case 1b: Follow-up or history response already assembled ───────────────
    if next_action in ("ask_followup", "history_response"):
        state["system_trace"] = _build_system_trace(state, next_action)
        return state

    # ── Case 2: Emergency interrupt ────────────────────────────────────────────
    if next_action == "priority_interrupt":
        messages = state.get("messages", [])
        last_msg = messages[-1].get("content", "") if messages else ""
        normalized = _apply_calm_tone(last_msg, state.get("risk_level", "unknown"))
        state["formatted_response"] = normalized
        state["final_response"]     = normalized
        state["system_trace"]       = _build_system_trace(state, next_action)
        return state

    # ── Case 3: Body image detailed response path ──────────────────────────────
    # Keep body-image output richly contextual while preserving standard
    # formatter behavior for medical_report and all other intents.
    if intent == "body_image":
        formatted = _build_body_image_response(state)
        state["formatted_response"] = formatted
        state["final_response"] = formatted
        state["messages"] = _update_message_history(state, formatted)
        state["system_trace"] = _build_system_trace(state, next_action)

        log_event(
            logger,
            "response_formatted_body_image",
            risk_level=state.get("risk_level", "low"),
            response_length=len(formatted),
            sections=formatted.count("###"),
        )
        return state

    # ── Case 4: Standard 7-section response (non-body-image intents) ─────────
    # medical_report follows this default path.

    llm_output = state.get("llm_output", {}) or {}
    urgency    = state.get("urgency", "routine")
    risk_level = state.get("risk_level", "low")
    symptoms   = state.get("symptoms", []) or []

    # Get nutrition output (only include for moderate+ risk)
    risk_lower = risk_level.lower()
    nutrition_output = (
        state.get("nutrition_output")
        if risk_lower in ("moderate", "high", "critical")
        else None
    )

    # Set nutrition_image_required if nutrition_output is present and real
    if nutrition_output and nutrition_output.get("_source") != "fallback":
        state["nutrition_image_required"] = True

    # Detect if this is a critical/emergency case
    is_critical = (
        next_action == "priority_interrupt"
        or risk_lower == "critical"
        or urgency.lower() in ("emergency", "critical")
        or state.get("red_flag_triggered", False)
    )

    # If llm_output is empty (vision fallback path), pull from last message
    if not llm_output:
        vision = state.get("vision_findings", {}) or {}
        fallback_summary = (
            str(vision.get("explanation", "") or "").strip()
            or "Based on the available information, this may be a minor skin-related issue."
        )
        fallback_causes = vision.get("possible_conditions", []) or []
        fallback_output = {
            "clinical_summary": fallback_summary,
            "possible_causes": [str(c) for c in fallback_causes[:5]],
            "risk_level": risk_level,
            "recommended_action": (
                "Please keep the area clean and dry, avoid irritants, and consult a doctor if symptoms worsen."
            ),
            "urgency": urgency,
            "confidence_score": float(vision.get("confidence", 0.5) or 0.5),
            "suggested_otc": None,
            "nutrition_tip": None,
        }

        formatted = build_response(
            symptoms=symptoms,
            llm_output=fallback_output,
            risk_level=risk_level,
            urgency=urgency,
            followup_question=None,
            nutrition_output=nutrition_output,
            is_critical=is_critical,
        )

        state["formatted_response"] = formatted
        state["final_response"]     = formatted
        state["messages"]           = _update_message_history(state, formatted)
        state["system_trace"]       = _build_system_trace(state, next_action)
        return state

    # Build 7-section formatted response
    formatted = build_response(
        symptoms=symptoms,
        llm_output=llm_output,
        risk_level=risk_level,
        urgency=urgency,
        followup_question=None,
        nutrition_output=nutrition_output,
        is_critical=is_critical,
    )

    state["formatted_response"] = formatted
    state["final_response"]     = formatted
    state["messages"]           = _update_message_history(state, formatted)
    state["system_trace"]       = _build_system_trace(state, next_action)

    log_event(logger, "response_formatted",
              urgency=urgency,
              risk_level=risk_level,
              response_length=len(formatted),
              sections=formatted.count("###"))
    return state
