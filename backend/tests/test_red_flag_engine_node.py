from backend.src.nodes.red_flag_engine_node import red_flag_engine_node
from backend.tests.helpers import make_state

def test_red_flag_skipped_empty_state():
    state = make_state(symptoms=[], user_input="", reasoning_input="", extracted_text="")
    result = red_flag_engine_node(state)
    assert result["red_flag_triggered"] is False
    assert result["urgency"] == "routine"

def test_routine_case():
    state = make_state(user_input="I have a mild fever and a sore throat", risk_level="low")
    result = red_flag_engine_node(state)
    assert result["red_flag_triggered"] is False
    assert result["urgency"] == "routine"
    assert result["risk_level"] == "low"

def test_critical_urgency_escalation():
    state = make_state(symptoms=["respiratory arrest"], risk_level="low")
    result = red_flag_engine_node(state)
    assert result["red_flag_triggered"] is True
    assert result["urgency"] == "critical"
    assert result["risk_level"] == "critical"

def test_emergency_severity():
    state = make_state(user_input="I am experiencing chest pain", risk_level="low")
    result = red_flag_engine_node(state)
    assert result["red_flag_triggered"] is True
    assert result["urgency"] == "emergency"
    assert result["risk_level"] == "high"

def test_urgent_severity():
    state = make_state(symptoms=["high fever", "severe headache"], risk_level="low")
    result = red_flag_engine_node(state)
    assert result["red_flag_triggered"] is True
    assert result["urgency"] == "urgent"
    assert result["risk_level"] == "moderate"

def test_multiple_matching_severities():
    # Matches both emergency ("chest pain") and urgent ("high fever")
    state = make_state(user_input="I have a high fever and chest pain", risk_level="low")
    result = red_flag_engine_node(state)
    assert result["red_flag_triggered"] is True
    # Should escalate to the highest matching risk/urgency
    assert result["urgency"] == "emergency"
    assert result["risk_level"] == "high"
