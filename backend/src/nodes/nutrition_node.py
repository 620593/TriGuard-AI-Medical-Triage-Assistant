"""
nutrition_node.py  (Version 3 — NEW)
--------------------------------------
Generates dietary suggestions for LOW and MODERATE risk patients.
Optionally generates a meal image if HF_API_TOKEN is available.

This node runs AFTER judge_validator_node, only for non-critical cases.
"""

from backend.src.tools.nutrition_image_tool import generate_nutrition_advice
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

import asyncio

logger = get_logger("nutrition")


async def nutrition_node(state: TriageState) -> TriageState:
    """
    Generates nutrition advice for low/moderate risk patients.

    Args:
        state: Contains symptoms and risk_level.

    Returns:
        TriageState: Updated with nutrition_advice and optional nutrition_image.
    """
    risk_level = state.get("risk_level", "").lower()

    # Only generate nutrition advice for low and moderate risk
    if risk_level not in ("low", "moderate"):
        state["nutrition_advice"] = ""
        state["nutrition_image"] = ""
        return state

    symptoms = state.get("symptoms", [])

    try:
        result = await asyncio.to_thread(generate_nutrition_advice, symptoms=symptoms, risk_level=risk_level)
        state["nutrition_advice"] = result.get("advice", "")
        state["nutrition_image"] = result.get("image_url", "")

        log_event(logger, "nutrition_generated",
                  risk_level=risk_level,
                  has_image=bool(result.get("image_url")))

    except Exception as e:
        log_event(logger, "nutrition_failed", error=str(e))
        state["nutrition_advice"] = ""
        state["nutrition_image"] = ""

    return state
