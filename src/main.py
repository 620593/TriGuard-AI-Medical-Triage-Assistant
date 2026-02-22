"""
main.py  (Version 2 — Conversation Loop Fix)
---------------------------------------------
Entry point for the TriGuard AI Medical Triage MVP v2.

Usage:
    python -m src.main          # Continue existing session
    python -m src.main --new    # Start a fresh session (clears history.json)

CONVERSATION LOOP (key design):
    The graph may pause after followup_node (next_action == 'ask_followup'),
    save state, and return to the caller. Without a loop, the program would
    exit immediately after printing the question.

    The while-loop here:
      1. Invokes the graph with the current state.
      2. Prints the latest assistant message.
      3. If next_action == 'ask_followup': collects the user's reply,
         appends it to state["messages"], sets _mid_session=True so
         load_history_node skips disk reload, and loops again.
      4. Otherwise: triage is complete → exit.

    _mid_session flag:
        Initialised False before the first graph invocation (load from disk).
        Set to True when appending a follow-up reply before re-invoking the
        graph. This tells load_history_node to skip disk reload, preventing
        the same history messages being prepended again every iteration.

Environment variables (set in .env):
    GROQ_API_KEY   : https://console.groq.com
    TAVILY_API_KEY : https://app.tavily.com
"""

import sys
from dotenv import load_dotenv

# Load .env BEFORE importing any module that reads API keys at call time
load_dotenv()

from src.graph.builder import build_triage_graph
from src.state.state import TriageState


def main():
    """
    Runs the full conversational triage session with a follow-up loop.
    """
    print("\n" + "=" * 62)
    print("  TriGuard AI — Medical Triage Assistant (v2)")
    print("=" * 62)
    print("  ⚠️  Triage tool only. NOT a substitute for medical advice.")
    print("  Type your symptoms, or 'quit' to exit.")
    print("=" * 62 + "\n")

    new_session = "--new" in sys.argv

    # ── Collect the opening user message ──────────────────────────────────────
    first_input = input("You: ").strip()
    if not first_input or first_input.lower() == "quit":
        print("Goodbye!")
        sys.exit(0)

    # ── Build initial state ────────────────────────────────────────────────────
    # _mid_session starts False — load_history_node will load disk on this turn.
    # next_action = 'new_session' → load_history_node wipes old history.
    state: TriageState = {
        "messages":           [{"role": "user", "content": first_input}],
        "symptoms":           [],
        "followup_count":     0,
        "retrieved_info":     [],
        "risk_score":         0.0,
        "risk_level":         "",
        "risk_confidence":    0.0,
        "mental_health_flag": False,
        "next_action":        "new_session" if new_session else "",
        "_mid_session":       False,    # First turn always loads history from disk
    }

    # Build graph once — reused across all loop iterations (no re-compilation)
    app = build_triage_graph()

    # ── Conversation loop ──────────────────────────────────────────────────────
    while True:
        # Invoke the LangGraph pipeline; graph returns updated state
        state = app.invoke(state)

        # Print the latest assistant message (follow-up question or final response)
        assistant_msgs = [m for m in state["messages"] if m.get("role") == "assistant"]
        if assistant_msgs:
            print("\n" + "-" * 62)
            print("\n" + assistant_msgs[-1]["content"])
            print("\n" + "=" * 62 + "\n")
        else:
            print("No response generated. Please try again.")
            break

        # ── Triage complete — exit loop ────────────────────────────────────────
        if state.get("next_action") != "ask_followup":
            break

        # ── Follow-up: collect user reply and loop back into graph ─────────────
        user_reply = input("You: ").strip()
        if not user_reply or user_reply.lower() == "quit":
            print("Session ended. Goodbye!")
            break

        # Append the user's reply to the ongoing conversation
        state["messages"].append({"role": "user", "content": user_reply})

        # Signal load_history_node to skip disk reload this iteration.
        # (State is already correct in memory; re-reading would duplicate messages.)
        state["_mid_session"] = True

        # Clear routing signal so the graph routes normally on re-entry
        state["next_action"] = ""


if __name__ == "__main__":
    main()
