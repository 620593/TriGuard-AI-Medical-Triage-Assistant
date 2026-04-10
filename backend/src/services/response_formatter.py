"""
response_formatter.py  (Version 1 — Strict Section Format)
-----------------------------------------------------------
Pure presentation service. Produces the strict 7-section chatbot-style format.

Section order:
  1. 🧾 Symptoms Identified
  2. 🩺 Possible Conditions
  3. ❓ Follow-Up Questions          (only if needed)
  4. 🧘 Recommended Actions
  5. 🥗 Nutrition Advice
  6. 💊 OTC Suggestions              (only if safe + applicable)
  7. 🚨 When to See a Doctor

Rules:
  - NEVER hallucinate conditions unrelated to listed symptoms.
  - NEVER use heavy medical jargon — use user-friendly language.
  - NEVER panic the user. Always calm, even for critical cases.
  - Each section separated by --- divider.
  - If a section has no content, it is OMITTED entirely.
  - No LLM calls. Pure deterministic string building.
"""

from typing import Optional
import re

_SEP = "\n\n---\n\n"

# Medical jargon → simple replacements
_JARGON_MAP = {
    "gastrointestinal discomfort": "stomach discomfort",
    "gastrointestinal": "stomach/digestive",
    "pharyngitis": "throat infection",
    "pyrexia": "fever",
    "myalgia": "muscle pain",
    "dyspnea": "difficulty breathing",
    "hypertension": "high blood pressure",
    "tachycardia": "fast heartbeat",
    "edema": "swelling",
    "prognosis": "how things may go",
    "acute": "sudden/severe",
    "chronic": "long-lasting",
    "lesion": "skin change",
    "inflammation": "swelling and irritation",
    "viral infection": "infection caused by a virus",
    "bacterial infection": "infection caused by bacteria",
    "aetiology": "cause",
    "etiology": "cause",
    "pathology": "health condition",
    "comorbidity": "other existing condition",
    "contraindicated": "not safe to use",
    "differential diagnosis": "possible causes",
    "clinical presentation": "your symptoms",
    "consult a physician": "see a doctor",
    "administer": "take",
    "analgesic": "painkiller",
    "antipyretic": "fever-reducing medicine",
    "antihistamine": "allergy medicine",
    "prophylactic": "preventive",
    "systemic": "whole-body",
    "subcutaneous": "just under the skin",
    "erythema": "redness",
    "pruritus": "itching",
    "urticaria": "hives",
    "dermatitis": "skin irritation",
}

# Calm alternatives for scary/alarming phrases
_CALM_REPLACEMENTS = {
    "MUST seek": "should seek",
    "immediately go": "please go",
    "life-threatening": "potentially serious",
    "do not delay": "please don't wait",
    "call 911": "call emergency services",
    "call 999": "call emergency services",
    "critical condition": "serious condition",
    "fatal": "very serious",
    "dangerous": "concerning",
    "alarming": "worth attention",
    "extreme risk": "high risk",
    "could be deadly": "needs urgent attention",
    "you may die": "this is very serious",
    "severe emergency": "urgent situation",
}


def _simplify(text: str) -> str:
    """Applies jargon map + calm replacements to any string."""
    if not text:
        return ""
    for jargon, simple in _JARGON_MAP.items():
        text = text.replace(jargon, simple)
        text = text.replace(jargon.title(), simple.title())
    for scary, calm in _CALM_REPLACEMENTS.items():
        text = text.replace(scary, calm)
    return text


def _bullets(items: list, max_items: int = 6) -> str:
    """Formats a list as bullet lines."""
    return "\n".join(
        f"• {_simplify(str(item).strip())}"
        for item in items[:max_items]
        if str(item).strip()
    )


def _extract_age_in_months(text: str) -> int | None:
    """Best-effort age extraction from unstructured text."""
    if not text:
        return None

    t = text.lower()
    m = re.search(r"\b(\d{1,2})\s*(?:month|months|mo|mos)\s*(?:old)?\b", t)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    y = re.search(r"\b(\d{1,2})\s*(?:year|years|yr|yrs)\s*(?:old)?\b", t)
    if y:
        try:
            return int(y.group(1)) * 12
        except ValueError:
            return None

    return None


def _is_infant_context(symptoms: list, llm_output: dict) -> bool:
    """Detect infant context (<12 months) from available response inputs."""
    summary = str(llm_output.get("clinical_summary", "") or "")
    causes = " ".join(str(c) for c in (llm_output.get("possible_causes", []) or []))
    symptom_text = " ".join(str(s) for s in (symptoms or []))
    blob = f"{summary} {causes} {symptom_text}".strip()

    months = _extract_age_in_months(blob)
    if months is not None and months < 12:
        return True

    low = blob.lower()
    return "infant" in low or "newborn" in low


def _build_infant_nutrition_section() -> str:
    """Returns a conservative infant-safe nutrition block."""
    return (
        "### 🥗 Nutrition Advice\n"
        "**Infant feeding guidance (<12 months):**\n"
        "• Primary nutrition should be breast milk or iron-fortified infant formula\n"
        "• If solids were already started, use small age-appropriate purees only\n"
        "• Do not give spicy/fried foods or home-remedy foods meant for older children\n"
        "• Do not give honey before 12 months\n\n"
        "💧 Continue regular breast milk/formula feeds and watch hydration closely.\n"
        "🏃 If feeding drops, fever continues, breathing changes, or urine output decreases, contact a pediatrician promptly."
    )


def build_response(
    symptoms: list,
    llm_output: dict,
    risk_level: str,
    urgency: str,
    followup_question: Optional[str] = None,
    nutrition_output: Optional[dict] = None,
    is_critical: bool = False,
) -> str:
    """
    Builds the full 7-section chatbot response string.

    Args:
        symptoms:           Extracted symptom list.
        llm_output:         Dict from llm_brain_node (clinical_summary, possible_causes, etc.).
        risk_level:         Current risk level (low/moderate/high/critical).
        urgency:            Current urgency (routine/urgent/emergency/critical).
        followup_question:  Optional LLM-generated follow-up question text.
        nutrition_output:   Optional nutrition dict from nutrition_node.
        is_critical:        Forces the emergency guidance message.

    Returns:
        Formatted multi-section string.
    """
    risk_lower = risk_level.lower()
    urgency_lower = urgency.lower()
    sections: list[str] = []

    # ── SECTION 1: Symptoms Identified ────────────────────────────────────────
    if symptoms:
        sym_lines = _bullets(symptoms, max_items=8)
        sections.append(f"### 🧾 Symptoms Identified\n{sym_lines}")
    else:
        sections.append("### 🧾 Symptoms Identified\n• No specific symptoms detected yet. Please describe how you're feeling.")

    # ── SECTION 2: Possible Conditions ────────────────────────────────────────
    causes = llm_output.get("possible_causes", [])
    summary = _simplify(llm_output.get("clinical_summary", "").strip())

    if causes or summary:
        cond_lines = []
        if summary:
            cond_lines.append(summary)
        if causes:
            cond_lines.append("")
            for cause in causes[:5]:
                cause_str = _simplify(str(cause).strip())
                cond_lines.append(f"• {cause_str} *(Possible but not confirmed)*")
        sections.append("### 🩺 Possible Conditions\n" + "\n".join(cond_lines))

    # ── SECTION 3: Follow-Up Questions (only if needed) ───────────────────────
    if followup_question:
        sections.append(f"### ❓ Follow-Up Questions\n{_simplify(followup_question)}")

    # ── SECTION 4: Recommended Actions ────────────────────────────────────────
    action = llm_output.get("recommended_action", "").strip()
    action = _simplify(action)
    if action:
        # Parse into bullet items
        action_items = []
        for item in action.replace(";", ".").split("."):
            item = item.strip()
            if item and len(item) > 8:
                action_items.append(item)

        if action_items:
            action_block = _bullets(action_items, max_items=5)
        else:
            action_block = f"• {action}"

        sections.append(f"### 🧘 Recommended Actions\n{action_block}")

    # ── SECTION 5: Nutrition Advice ───────────────────────────────────────────
    # From LLM tip or full nutrition_node output
    if _is_infant_context(symptoms, llm_output):
        sections.append(_build_infant_nutrition_section())
    else:
        nutrition_tip = _simplify(llm_output.get("nutrition_tip", "") or "")
        nutrition_lines = []

        if nutrition_output and isinstance(nutrition_output, dict):
            recs   = nutrition_output.get("dietary_recommendations", [])
            avoids = nutrition_output.get("foods_to_avoid", [])
            hydra  = _simplify(str(nutrition_output.get("hydration_advice", "")).strip())
            life   = _simplify(str(nutrition_output.get("lifestyle_advice", "")).strip())

            if recs:
                nutrition_lines.append("**What to eat / drink:**")
                nutrition_lines.append(_bullets(recs, max_items=4))
            if avoids:
                nutrition_lines.append("\n**What to avoid:**")
                nutrition_lines.append(_bullets(avoids, max_items=3))
            if hydra:
                nutrition_lines.append(f"\n💧 {hydra}")
            if life:
                nutrition_lines.append(f"\n🏃 {life}")
        elif nutrition_tip:
            nutrition_lines.append(nutrition_tip)

        if nutrition_lines:
            sections.append("### 🥗 Nutrition Advice\n" + "\n".join(nutrition_lines))

    # ── SECTION 6: OTC Suggestions ────────────────────────────────────────────
    # Only show OTC for low/moderate risk (never for high/critical)
    suggested_otc = llm_output.get("suggested_otc")
    if suggested_otc and risk_lower in ("low", "moderate"):
        otc_text = _simplify(str(suggested_otc))
        otc_block = (
            f"{otc_text}\n\n"
            "⚠️ *These are common over-the-counter options. "
            "Take as per package instructions. "
            "Do not take if pregnant, have kidney/liver issues, or are on other medicines — ask a pharmacist first. "
            "Stop if symptoms worsen.*"
        )
        sections.append(f"### 💊 OTC Suggestions\n{otc_block}")

    # ── SECTION 7: When to See a Doctor ──────────────────────────────────────
    when_to_see = _build_doctor_guidance(risk_lower, urgency_lower, is_critical)
    sections.append(f"### 🚨 When to See a Doctor\n{when_to_see}")

    # ── Join sections with separator ──────────────────────────────────────────
    return _SEP.join(sections)


def _build_doctor_guidance(risk_level: str, urgency: str, is_critical: bool) -> str:
    """Returns calm, clear guidance about when to seek medical care."""
    if is_critical or urgency in ("emergency", "critical") or risk_level == "critical":
        return (
            "This may need urgent attention. Please stay calm. "
            "We recommend contacting emergency services or going to the nearest emergency room right away. "
            "You are doing the right thing by seeking help."
        )
    elif risk_level == "high" or urgency == "urgent":
        return (
            "Please try to see a doctor today or go to an urgent care centre. "
            "Your symptoms deserve proper attention soon. "
            "If you feel significantly worse, don't wait — go to emergency care."
        )
    elif risk_level == "moderate":
        return (
            "Consider seeing a doctor within the next 1–2 days if your symptoms continue or worsen. "
            "You don't need to rush, but don't ignore persistent symptoms."
        )
    else:
        # Low risk
        return (
            "Your symptoms appear manageable for now. Rest, stay hydrated, and monitor how you feel. "
            "If symptoms last more than 3 days or get worse, please consult a doctor."
        )


def build_history_response(user_reports: list) -> str:
    """
    Formats past health reports into a clean, readable chatbot-style response.

    Args:
        user_reports: List of report dicts from MongoDB.

    Returns:
        Formatted history string.
    """
    if not user_reports:
        return (
            "### 📋 Your Past Health Records\n\n"
            "No past health records found for your account. "
            "Your future consultations will be saved here automatically."
        )

    lines = ["### 📋 Your Past Health Records\n"]
    for i, report in enumerate(user_reports[:5], start=1):
        date = str(report.get("created_at", "Unknown date"))
        if "T" in date:
            date = date.split("T")[0]
        elif " " in date:
            date = date.split(" ")[0]

        risk    = report.get("risk_level", "unknown").upper()
        symptoms = ", ".join(report.get("symptoms", [])) or "Not recorded"
        summary  = _simplify(report.get("clinical_summary", report.get("summary", "No summary available.")))

        lines.append(f"**Consultation {i} — {date}**")
        lines.append(f"• Risk Level: {risk}")
        lines.append(f"• Symptoms: {symptoms}")
        lines.append(f"• Summary: {summary[:300]}")
        lines.append("")

    lines.append("*TriGuard stores your history to give you better, more personalised health guidance.*")
    return "\n".join(lines)
