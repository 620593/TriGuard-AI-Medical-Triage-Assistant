"""
presentation_formatter.py  (Version 6)
-----------------------------------------
Pure presentation-layer formatters for response_node.

Responsibility:
    - String formatting only.
    - No state access.
    - No LLM calls.
    - No side effects.

All functions are pure — they take data values and return strings.
response_node imports from here to keep itself focused on
graph orchestration only.
"""

from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def is_safe_url(url: str) -> bool:
    """Validates URL safety (prevents SSRF/XSS)."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in _ALLOWED_SCHEMES
            and bool(parsed.netloc)
            and "javascript:" not in url.lower()
        )
    except Exception:
        return False


def risk_badge(risk_level: str) -> str:
    """Returns a friendly emoji + label for risk level."""
    mapping = {
        "low":      "🟢 LOW",
        "moderate": "🟡 MODERATE",
        "high":     "🔴 HIGH",
        "critical": "🔴 CRITICAL",
        "unknown":  "⚪ UNKNOWN",
    }
    return mapping.get(risk_level.lower(), f"⚪ {risk_level.upper()}")


def risk_closing_line(risk_level: str, urgency: str) -> str:
    """
    Returns the closing guidance line based on risk + urgency.
    Warm, calibrated language — not robotic, not dramatic.
    """
    urgency_lower = urgency.lower()
    risk_lower    = risk_level.lower()

    if urgency_lower in ("emergency", "critical") or risk_lower in ("high", "critical"):
        return (
            "🚨 Please stop and seek emergency care right now. "
            "Call emergency services (911 / 999 / 112) or have someone drive you "
            "to the nearest emergency room. Do not wait."
        )
    elif urgency_lower == "urgent" or risk_lower == "moderate":
        return (
            "📋 It would be a good idea to speak with a doctor today if you can. "
            "Your symptoms don't necessarily mean something serious, but they deserve "
            "proper attention — please don't ignore them if they get worse."
        )
    else:
        return (
            "🌿 Your symptoms appear manageable at this stage. Keep an eye on how "
            "you're feeling, stay hydrated, rest when you can, and reach out to a "
            "healthcare provider if anything changes or you feel uncertain."
        )


def format_bullets(items: list, max_items: int = 5) -> str:
    """Formats a list as bullet lines."""
    return "\n".join(f"• {item}" for item in items[:max_items] if item)


def parse_action_items(action) -> list:
    """
    Normalises the recommended_action field into a clean list of bullet strings.
    Handles both str (period/semicolon delimited) and list inputs.
    """
    if isinstance(action, list):
        return [str(a).strip() for a in action if str(a).strip()]
    if isinstance(action, str):
        items = [
            a.strip() for a in action.replace(";", ".").split(".")
            if a.strip() and len(a.strip()) > 8
        ]
        return items if items else ([action] if action else ["Monitor your symptoms carefully."])
    return ["Monitor your symptoms carefully."]


def format_vision_section(vision_findings: dict) -> str:
    """
    Renders a structured 🔬 Visual Analysis section from vision_findings dict.
    Returns empty string if no usable vision data.
    """
    if not vision_findings or not isinstance(vision_findings, dict):
        return ""

    image_type        = vision_findings.get("image_type", "").upper()
    visual_findings   = vision_findings.get("visual_findings", [])
    lesion_morphology = vision_findings.get("lesion_morphology") or ""
    color_description = vision_findings.get("color_description") or ""
    distribution      = vision_findings.get("distribution") or ""
    severity          = vision_findings.get("severity") or ""
    possible_cond     = vision_findings.get("possible_conditions", [])
    confidence        = vision_findings.get("confidence", 0.0)

    # Don't render the section if findings are empty
    if not any([visual_findings, lesion_morphology, color_description, distribution]):
        return ""

    lines = [
        "",
        f"🔬 Image Analysis — {image_type or 'SKIN'} Findings",
        "─" * 40,
        f"Analysis confidence: {confidence:.0%}",
        "",
    ]

    if visual_findings:
        lines.append("Observed findings:")
        for item in visual_findings[:6]:
            lines.append(f"  • {item}")
        lines.append("")

    details = []
    if lesion_morphology:
        details.append(f"🔵 Lesion type: {lesion_morphology}")
    if color_description:
        details.append(f"🎨 Color: {color_description}")
    if distribution:
        details.append(f"🗺️ Distribution: {distribution}")
    if severity:
        severity_emoji = {"mild": "🟢", "moderate": "🟡", "severe": "🔴"}.get(severity.lower(), "▪️")
        details.append(f"{severity_emoji} Severity: {severity.capitalize()}")

    if details:
        lines.extend(details)
        lines.append("")

    if possible_cond:
        lines.append("Possible conditions (for discussion with your doctor):")
        for cond in possible_cond[:5]:
            lines.append(f"  • {cond}")
        lines.append("")

    return "\n".join(lines)


def apply_tone(llm_output: dict, urgency: str, vision_findings: dict = None) -> str:
    """
    Converts llm_output into a warm, structured, human-friendly response.
    Fully deterministic — no LLM delegation.

    Sections:
        🩺 Triage Summary
        🔬 Image Analysis (vision cases only)
        🔎 What Might Be Happening
        🧭 What You Can Do
        📊 Risk Level
        Closing guidance line
    """
    summary     = llm_output.get("clinical_summary", "").strip()
    causes      = llm_output.get("possible_causes", [])
    action      = llm_output.get("recommended_action", "").strip()
    risk_level  = llm_output.get("risk_level", "unknown")
    confidence  = llm_output.get("confidence_score", 0.0)

    # ── Intro line — warm, not robotic ────────────────────────────────────────
    intro = (
        f"Based on what you've shared, {summary[0].lower()}{summary[1:]}"
        if summary and len(summary) > 1
        else "Based on what you've shared, I've reviewed your image and symptoms carefully."
    )

    action_items  = parse_action_items(action)
    causes_block  = format_bullets(causes, max_items=4)
    actions_block = format_bullets(action_items, max_items=5)
    badge         = risk_badge(risk_level)
    closing_line  = risk_closing_line(risk_level, urgency)

    lines = [
        "🩺 Triage Summary",
        "─" * 40,
        intro,
        "",
    ]

    # ── Vision findings section (for image analysis) ──────────────────────
    if vision_findings:
        vision_section = format_vision_section(vision_findings)
        if vision_section:
            lines.append(vision_section)

    if causes_block:
        lines += [
            "🔎 What Might Be Happening",
            causes_block,
            "",
        ]

    if actions_block:
        lines += [
            "🧭 What You Can Do",
            actions_block,
            "",
        ]

    lines += [
        f"📊 Risk Level: {badge}",
        f"   (Assessment confidence: {confidence:.0%})",
        "",
        closing_line,
    ]

    return "\n".join(lines)


def format_nutrition_section(nutrition_out: dict) -> str:
    """
    Formats nutrition_output into the 🍎 Nutrition Support section.
    Returns empty string if no usable data.
    """
    if not nutrition_out:
        return ""

    raw_rec   = nutrition_out.get("dietary_recommendations", [])
    raw_avoid = nutrition_out.get("foods_to_avoid", [])
    hydration = str(nutrition_out.get("hydration_advice", "")).strip()
    lifestyle = str(nutrition_out.get("lifestyle_advice", "")).strip()

    rec   = raw_rec   if isinstance(raw_rec, list)   else [str(raw_rec)]
    avoid = raw_avoid if isinstance(raw_avoid, list) else [str(raw_avoid)]

    lines = ["", "🍎 Nutrition Support", "─" * 40]

    if rec:
        lines.append("Recommended foods & habits:")
        lines.append(format_bullets(rec, max_items=5))

    if avoid:
        lines.append("\nFoods and habits to avoid:")
        lines.append(format_bullets(avoid, max_items=4))

    if hydration:
        lines.append(f"\n💧 Hydration: {hydration}")

    if lifestyle:
        lines.append(f"\n🏃 Lifestyle tip: {lifestyle}")

    lines.append(
        "\n📸 A personalised nutrition visual guide is being generated "
        "and will appear shortly."
    )

    return "\n".join(lines)
