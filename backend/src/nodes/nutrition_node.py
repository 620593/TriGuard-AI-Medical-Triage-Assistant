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


async def nutrition_node(state: TriageState) -> TriageState:
    """
    Generates structured nutrition advice using Gemini 3.1.
    """
    risk_level = state.get("risk_level", "").lower()
    clinical_summary = state.get("llm_output", {}).get("clinical_summary", "")
    symptoms = state.get("symptoms", [])

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
        state["nutrition_output"]         = parsed
        log_event(logger, "nutrition_generated", status="success")
    except Exception as e:
        logger.error(f"Failed to parse nutrition JSON: {e}")

    return state
