"""
symptom_extraction_node.py  (NEW — Version 2)
----------------------------------------------
Uses Groq LLaMA to extract a clean, structured symptom list from user input.

Why it exists:
    V1 used a dumb keyword splitter which missed phrased symptoms like
    "I feel short of breath" or "my chest hurts". LLaMA understands natural
    language and extracts clinically meaningful symptom terms.

Anti-hallucination:
    LLaMA is instructed to ONLY extract from the user's words.
    It must not add symptoms that weren't mentioned.

Input:
    state (TriageState): State with messages populated.

Returns:
    TriageState: State with state["symptoms"] replaced by LLaMA-extracted list.
"""

from src.tools.groq_llama_tool import call_llama
from src.state.state import TriageState


def symptom_extraction_node(state: TriageState) -> TriageState:
    """
    Extracts a clean symptom list from the latest user message using LLaMA.

    Args:
        state (TriageState): Contains conversation messages.

    Returns:
        TriageState: symptoms field replaced with LLaMA-extracted symptom keywords.
    """
    # Get the latest user message only (not the full conversation)
    user_messages = [m["content"] for m in state["messages"] if m.get("role") == "user"]
    if not user_messages:
        return state   # Nothing to extract from

    latest_input = user_messages[-1]

    # Strict prompt: extract only what the user said
    prompt = (
        "You are a medical symptom extractor. Your ONLY job is to list the symptoms "
        "mentioned by the patient. Do NOT add, infer, or invent symptoms.\n\n"
        "Output a comma-separated list of symptom phrases. "
        "If no symptoms are mentioned, output: none\n\n"
        f"Patient input: {latest_input}\n\n"
        "Symptoms:"
    )

    raw = call_llama(prompt, max_tokens=100)

    if not raw or raw.strip().lower() == "none":
        # No extraction possible — keep existing symptoms (if any)
        return state

    # Parse comma-separated list into clean tokens
    extracted = [s.strip().lower() for s in raw.split(",") if s.strip()]

    # Merge with previously collected symptoms (union, no duplicates)
    existing = set(state.get("symptoms", []))
    state["symptoms"] = list(existing | set(extracted))

    return state
