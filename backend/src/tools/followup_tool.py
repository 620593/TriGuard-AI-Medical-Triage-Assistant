"""
followup_tool.py
----------------
Generates one targeted clarifying question based on the symptoms already collected.
This is called by symptom_followup_node when more information is needed.
Hard rule: returns None if followup_count has already reached the limit (3).
"""

from langchain_core.tools import tool
from typing import List, Optional


MAX_FOLLOWUPS = 3  # Global cap on follow-up questions per session


@tool
def generate_followup_question(
    symptoms: List[str],
    followup_count: int
) -> Optional[str]:
    """
    Generates a single clarifying medical question if under the follow-up limit.

    Why it exists:
        To gather more symptom detail before running retrieval or risk scoring,
        without bombarding the user with too many questions.

    Args:
        symptoms      (list[str]): Symptoms already collected.
        followup_count (int)     : How many follow-up questions were already asked.

    Returns:
        str  : A clarifying question to ask the user, OR
        None : If the maximum follow-up count is already reached.
    """
    # Hard stop: do not ask more than MAX_FOLLOWUPS questions
    if followup_count >= MAX_FOLLOWUPS:
        return None

    # Build a simple, targeted clarifying question prompt
    if not symptoms:
        return "Can you describe what symptoms you are experiencing right now?"

    symptom_str = ", ".join(symptoms)

    # Ordered list of progressively deeper clarifying questions
    followup_templates = [
        f"How long have you been experiencing {symptom_str}? Is it getting better or worse?",
        f"Are you experiencing any additional symptoms alongside {symptom_str}, such as fever, nausea, or pain?",
        f"Do you have any known medical conditions, allergies, or recent illnesses that may be related to {symptom_str}?",
    ]

    # Return the question that matches the current follow-up round
    return followup_templates[followup_count]
