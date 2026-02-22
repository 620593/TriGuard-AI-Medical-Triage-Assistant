"""
state.py  (Version 2)
---------------------
Defines the shared state object passed through every LangGraph node.

New in V2:
  - risk_confidence  : float  — how confident the risk engine is (0.0-1.0)
  - mental_health_flag : bool — True if self-harm / crisis language detected
"""

from typing import TypedDict, List


class TriageState(TypedDict):
    """
    Central state object for the V2 medical triage pipeline.

    Fields:
      messages          : Full conversation history [{role, content}, ...].
      symptoms          : Clean symptom list extracted by LLaMA.
      followup_count    : Number of clarifying questions asked so far (max 3).
      retrieved_info    : Medical summaries from Tavily (max 3).
      risk_score        : 0.0 – 10.0 severity score.
      risk_level        : 'low' | 'moderate' | 'high' | 'critical'.
      risk_confidence   : 0.0 – 1.0, how certain the risk engine is.
      mental_health_flag: True if crisis / self-harm language detected.
      next_action       : Graph routing signal — '' | 'ask_followup' | 'priority_interrupt'.
    """

    messages:           List[dict]   # Conversation history
    symptoms:           List[str]    # LLaMA-extracted symptom keywords
    followup_count:     int          # Follow-up questions used (0-3)
    retrieved_info:     List[str]    # Tavily medical summaries
    risk_score:         float        # 0.0 – 10.0
    risk_level:         str          # 'low' | 'moderate' | 'high' | 'critical'
    risk_confidence:    float        # 0.0 – 1.0
    mental_health_flag: bool         # True = crisis detected
    next_action:        str          # Graph routing control signal
    _mid_session:       bool         # True = main.py loop already ran once;
                                     # tells load_history_node to skip disk reload
