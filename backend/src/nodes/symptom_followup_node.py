"""
symptom_followup_node.py
------------------------
Decides whether to ask a clarifying question or proceed with retrieval.

Logic:
  - If followup_count < 3 AND symptoms are still vague/empty → ask a follow-up.
  - Otherwise → allow the graph to continue to disease_retrieval_node.

This node calls generate_followup_question tool and sets next_action accordingly.
"""

from backend.src.tools.followup_tool import generate_followup_question
from backend.src.state.state import TriageState


# Minimum number of symptoms before we consider the input "sufficient"
MIN_SYMPTOMS_REQUIRED = 2


def symptom_followup_node(state: TriageState) -> TriageState:
    """
    Evaluates whether symptom information is sufficient or needs clarification.

    Why it exists:
        Asking the right follow-up question leads to more accurate risk scoring
        and reduces the chance of retrieving irrelevant medical content.

    Args:
        state (TriageState): Current pipeline state.

    Returns:
        TriageState: Updated state with optional follow-up question in messages
                     and next_action set to guide graph routing.
    """
    symptoms = state.get("symptoms", [])
    followup_count = state.get("followup_count", 0)

    # Determine if symptoms are insufficient for a confident retrieval
    symptoms_are_vague = len(symptoms) < MIN_SYMPTOMS_REQUIRED

    if symptoms_are_vague and followup_count < 3:
        # Ask a clarifying question
        question = generate_followup_question.invoke({
            "symptoms": symptoms,
            "followup_count": followup_count,
        })

        if question:
            # Append follow-up question to the conversation messages
            state["messages"].append({
                "role": "assistant",
                "content": question,
            })
            # Increment the follow-up counter
            state["followup_count"] = followup_count + 1
            # Signal the graph that we are waiting for more user input
            state["next_action"] = "ask_followup"

    else:
        # Symptoms are sufficient — proceed to Tavily retrieval
        state["next_action"] = ""  # Clear any previous action flag

    return state
