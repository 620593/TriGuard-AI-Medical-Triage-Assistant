"""
nutrition_node.py  (Version 6)
---------------------------------
Generates structured nutrition advice using Gemini 3.1.
Runs only for low/moderate risk when trigger_nutrition_node is True.
Outputs to state["nutrition_output"]
"""

import json
import re

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from backend.src.tools.gemini_tool import call_gemini

logger = get_logger("nutrition")


def _extract_age_in_months(text: str) -> int | None:
    """Extracts age in months from free text when present."""
    if not text:
        return None

    t = text.lower()

    month_match = re.search(r"\b(\d{1,2})\s*(?:month|months|mo|mos)\s*(?:old)?\b", t)
    if month_match:
        try:
            return int(month_match.group(1))
        except ValueError:
            return None

    year_match = re.search(r"\b(\d{1,2})\s*(?:year|years|yr|yrs)\s*(?:old)?\b", t)
    if year_match:
        try:
            return int(year_match.group(1)) * 12
        except ValueError:
            return None

    return None


def _is_infant_case(state: TriageState, clinical_summary: str) -> bool:
    """True when available context suggests patient age is under 12 months."""
    age_sources = [
        clinical_summary,
        str(state.get("user_input", "") or ""),
        str(state.get("reasoning_input", "") or ""),
    ]

    for src in age_sources:
        months = _extract_age_in_months(src)
        if months is not None and months < 12:
            return True

    combined = " ".join(age_sources).lower()
    return "infant" in combined or "newborn" in combined


def _infant_nutrition_template() -> dict:
    """Safe nutrition guidance for infants under 12 months."""
    return {
        "dietary_recommendations": [
            "Primary nutrition should be breast milk or iron-fortified infant formula",
            "Feed in small, frequent amounts and monitor wet diapers",
            "If solids are already started, use age-appropriate pureed foods only under pediatric guidance",
        ],
        "foods_to_avoid": [
            "Do not give spicy, fried, or heavily processed foods",
            "Do not give honey before 12 months",
            "Avoid cow's milk as the main drink before 12 months",
        ],
        "hydration_advice": "Continue breast milk or formula regularly. For signs of dehydration or poor feeding, contact a pediatrician urgently.",
        "lifestyle_advice": "Keep the baby rested, monitor temperature, and seek pediatric care promptly if feeding drops, breathing changes, or fever persists.",
        "confidence_score": 0.9,
        "_source": "infant_safety_guard",
    }


async def nutrition_node(state: TriageState) -> TriageState:
    """
    Generates structured nutrition advice using Gemini 3.1.
    """
    risk_level = state.get("risk_level", "").lower()
    clinical_summary = state.get("llm_output", {}).get("clinical_summary", "")
    symptoms = state.get("symptoms", [])
    infant_case = _is_infant_case(state, clinical_summary)

    age_safety_rules = (
        "Patient appears to be an infant (<12 months).\n"
        "Do NOT suggest adult or toddler foods (for example bananas, toast, spicy foods, herbal teas).\n"
        "Primary nutrition must be breast milk or infant formula.\n"
        "Use pediatric-safe, conservative guidance only.\n\n"
        if infant_case
        else "Provide age-appropriate conservative advice based on symptoms.\n\n"
    )

    prompt = (
        "System: You are a conservative clinical nutrition assistant.\n"
        "Provide evidence-based, safe, non-extreme dietary advice.\n"
        "Do not provide medical diagnosis.\n"
        "Avoid unsafe or radical diets.\n\n"
        "Patient condition:\n"
        f"{clinical_summary}\n\n"
        "Risk level:\n"
        f"{risk_level}\n\n"
        "Symptoms:\n"
        f"{symptoms}\n\n"
        "Age Safety Rules:\n"
        f"{age_safety_rules}"
        "Return STRICT JSON:\n"
        "{\n"
        '  "dietary_recommendations": [str],\n'
        '  "foods_to_avoid": [str],\n'
        '  "hydration_advice": str,\n'
        '  "lifestyle_advice": str,\n'
        '  "confidence_score": float\n'
        "}\n\n"
        "No markdown.\n"
        "No explanations.\n"
        "JSON only."
    )

    try:
        raw_text = await call_gemini(prompt, model_name="gemini-2.0-flash")
    except Exception as e:
        logger.error(f"Failed to get nutrition plan: {e}")
        if infant_case:
            state["nutrition_output"] = _infant_nutrition_template()
            log_event(logger, "nutrition_infant_guard_applied", reason="api_error")
            return state
        # FIX #10 — Text-based fallback when Gemini API fails
        state["nutrition_output"] = {
            "dietary_recommendations": [
                "Drink warm fluids like herbal tea and broths",
                "Eat light, easy-to-digest meals like rice, bananas, or toast",
                "Include fruits rich in Vitamin C like oranges and lemon",
                "Avoid spicy, fried, or processed foods until you recover",
            ],
            "foods_to_avoid": [
                "Spicy foods", "Alcohol", "Caffeine", "Cold beverages",
            ],
            "hydration_advice": "Drink at least 8 glasses of water daily. Oral rehydration salts (ORS) are helpful if you feel weak.",
            "lifestyle_advice": "Rest well. Avoid strenuous activity. Sleep at least 7-8 hours.",
            "confidence_score": 0.5,
            "_source": "fallback",  # internal marker
        }
        log_event(logger, "nutrition_fallback_used", reason="api_error", error=str(e))
        return state

    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1]) if len(lines) > 2 else raw_text

    try:
        m = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if m:
            raw_text = m.group()
        parsed = json.loads(raw_text)
        if infant_case:
            state["nutrition_output"] = _infant_nutrition_template()
            log_event(logger, "nutrition_infant_guard_applied", reason="parsed_output_override")
        else:
            state["nutrition_output"] = parsed
        log_event(logger, "nutrition_generated", status="success")
    except Exception as e:
        logger.error(f"Failed to parse nutrition JSON: {e}")
        if infant_case:
            state["nutrition_output"] = _infant_nutrition_template()
            log_event(logger, "nutrition_infant_guard_applied", reason="json_parse_error")
            return state
        # FIX #10 — Text-based fallback when JSON parse fails (DO NOT generate images)
        state["nutrition_output"] = {
            "dietary_recommendations": [
                "Drink warm fluids like herbal tea and clear soups",
                "Eat light, easy-to-digest foods like rice, bananas, and toast",
                "Include fruits rich in Vitamin C: oranges, lemon, guava",
            ],
            "foods_to_avoid": ["Spicy foods", "Fried food", "Alcohol", "Cold drinks"],
            "hydration_advice": "Drink at least 8 glasses of water daily. Try ORS if feeling weak.",
            "lifestyle_advice": "Rest well, sleep 7-8 hours, avoid strenuous activity.",
            "confidence_score": 0.4,
            "_source": "fallback",
        }
        log_event(logger, "nutrition_fallback_used", reason="json_parse_error", error=str(e))

    return state
