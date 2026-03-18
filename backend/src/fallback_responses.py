"""
fallback_responses.py  (V5 DOCUMENT PIPELINE UPGRADE)
-------------------------------------------------------
Centralised library of structured fallback response strings.

Responsibility: presentation/formatting only.
This module is intentionally free of side-effects — it returns strings and
never touches state directly. llm_brain_node imports from here so that it
remains a pure reasoning node (no hardcoded UI strings in reasoning code).

# 🔥 V5 DOCUMENT PIPELINE UPGRADE:
    Added vision_error_response() and empty_input_response() to handle
    V5 pipeline failure states cleanly, separate from LLM reasoning logic.
"""



def vision_error_response() -> str:
    """
    # 🔥 V5 DOCUMENT PIPELINE UPGRADE
    Returns a structured user-facing message when vision API fails.
    Called by llm_brain_node when state['vision_error'] is True.

    Reasons for failure: model_decommissioned, API 400, timeout,
    image too large, or zero-confidence unknown result.
    """
    return (
        "⚠️ I was unable to analyse your image at this time.\n\n"
        "This could be due to:\n"
        "  • The image format not being supported (use JPG or PNG).\n"
        "  • A temporary issue with the image analysis service.\n\n"
        "💡 Please try again with a clearer image, or describe your symptoms in text.\n"
        "DISCLAIMER: This is a triage tool only. Consult a doctor for medical advice."
    )


def empty_input_response(risk_level: str = "unknown") -> str:
    """
    # 🔥 V5 DOCUMENT PIPELINE UPGRADE
    Returns a structured Triage-format fallback when no user input is present.
    Called by llm_brain_node when user_input is empty and message history is empty.

    This ensures judge_validator always receives a non-blank response that
    conforms to the expected SUMMARY/RISK_LEVEL/ACTION/RED_FLAGS format.
    """
    return (
        "SUMMARY: Your request could not be processed — no medical input was received.\n"
        f"RISK_LEVEL: {risk_level.upper()}\n"
        "RISK_SCORE: 0.0/10\n"
        "ACTION: Please describe your symptoms in text or re-upload a clearer image.\n"
        "RED_FLAGS: Worsening symptoms, difficulty breathing, chest pain, or confusion.\n"
        "DISCLAIMER: This is a triage tool only. Consult a doctor for medical advice."
    )


def ocr_failure_message() -> str:
    """
    # 🔥 V5 DOCUMENT PIPELINE UPGRADE
    Safe fallback message injected into state['user_input'] and messages
    when OCR extraction fails or returns empty text. Used by ocr_scan_node.
    """
    return (
        "I uploaded a medical document but the text could not be extracted. "
        "Please re-upload a clearer image or type the relevant information manually."
    )
