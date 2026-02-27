"""
helpers.py
----------
Shared test helper functions for TriGuard AI backend tests.
Importable from any test file via: from backend.tests.helpers import make_state
"""


def make_state(**kwargs) -> dict:
    """
    Builds a minimal valid TriageState dict for testing.
    Override any field by passing keyword arguments.
    """
    defaults = {
        "messages": [{"role": "user", "content": "I have a headache"}],
        "original_input": "I have a headache",
        "symptoms": [],
        "followup_count": 0,
        "retrieved_info": [],
        "risk_level": "low",
        "risk_score": 0.0,
        "risk_confidence": 0.0,
        "session_id": "test-session-123",
        "user_id": "test-user",
        "language": "en",
        "timestamp": "",
        "image_input": None,
        "input_mode": "text",
        "vision_findings": {},
        "mental_health_flag": False,
        "next_action": "",
        "judge_passed": True,
        "judge_feedback": "",
        "nutrition_advice": "",
        "nutrition_image": "",
        "audio_url": "",
        # ── V4 fields ────────────────────────────────────────────────────
        "intent": "",
        "disease_candidates": [],
        "svm_confidence": 0.0,
        "ocr_text": "",
        "xray_findings": {},
        "validated_response": "",
        "needs_nutrition_image": False,
        "final_response": "",
        "regeneration_count": 0,
        "force_accepted": False,
        "image_type_hint": "",
        "_mid_session": False,
    }
    defaults.update(kwargs)
    return defaults
