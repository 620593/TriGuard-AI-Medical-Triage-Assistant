"""
fallback_responses.py  (Version 6 — utils/)
---------------------------------------------
Centralised presentation-layer fallback strings.

Rules:
    - Pure functions only.
    - No state mutation.
    - No LLM calls.
    - No imports from nodes/ or tools/.

All user-facing fallback text lives here.
Reasoning nodes import from here — never inline strings.
"""

_DISCLAIMER = (
    "\n\n⚠️ DISCLAIMER: This is a triage tool only, NOT a medical diagnosis. "
    "Always consult a licensed physician for personal medical advice."
)


def vision_error_response() -> str:
    return (
        "🩺 We were unable to analyze your image at this time.\n\n"
        "This may be due to image quality, format, or a temporary service issue.\n\n"
        "💡 Please try uploading a clearer image, or describe your symptoms in text."
        + _DISCLAIMER
    )


def ocr_failure_message() -> str:
    return (
        "📄 We received your document but could not extract readable text from it.\n\n"
        "Please ensure the image is:\n"
        "  • Well-lit and clearly focused\n"
        "  • Not rotated or skewed\n"
        "  • Uploaded in JPG or PNG format\n\n"
        "Alternatively, you can type out your symptoms directly."
        + _DISCLAIMER
    )


def empty_input_response(risk_level: str = "unknown") -> str:
    return (
        f"It seems your message may not have come through clearly. "
        f"(Current risk level on file: {risk_level.upper()})\n\n"
        "Could you please describe your symptoms or concern in text? "
        "I'm here to help."
        + _DISCLAIMER
    )


def escalation_disabled_response() -> str:
    return (
        "🚨 High-risk symptoms detected. Please call emergency services "
        "(911 / 999 / 112) or go to your nearest emergency room immediately."
        + _DISCLAIMER
    )
