"""
vision_classifier_tool.py  (Version 5 — V5 UPGRADE)
------------------------------------------------------
Multi-purpose medical vision classifier using a multimodal LLM.
Handles skin, xray, and documents IN-MEMORY via base64.
Performance: Async-safe with AsyncGroq.

# 🔥 UPGRADE V5 changes:
    1. Structured document summary prompt: extracts document type, org/clinic name,
       handwritten flag, medications listed, patient details visibility.
    2. Granular error catching:
         - model_decommissioned (GroqError with 400 + "model_decommissioned")
         - API 400 bad request
         - Timeout / asyncio.TimeoutError
       All return structured safe fallback with confidence=0 + risk_level="unknown".
    3. Dedicated _build_document_prompt() and _build_body_prompt() for testability.
    4. VISION_API_TIMEOUT_SECONDS cap on all Groq calls.
"""

import os
import json
import base64
import asyncio
from typing import Dict, Any
from groq import AsyncGroq
from backend.src.logging.logger import get_logger

logger = get_logger("vision_classifier")

# ── Constants ─────────────────────────────────────────────────────────────────
_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
VISION_API_TIMEOUT_SECONDS = 30  # 🔥 UPGRADE V5: cap all Groq vision calls

# Lazy singleton for Async client
_async_client: AsyncGroq | None = None


def _get_async_client() -> AsyncGroq:
    global _async_client
    if _async_client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
        _async_client = AsyncGroq(api_key=api_key)
    return _async_client


def _get_mime_type(image_bytes: bytes) -> str:
    """Detects MIME type from magic bytes."""
    if image_bytes.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    if image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    if image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
        return "image/gif"
    if image_bytes.startswith(b'BM'):
        return "image/bmp"
    return "image/jpeg"


def _normalize_image_to_data_url(image_input: Any) -> str:
    """Normalizes bytes, data URL, or raw base64 to a data URL string."""
    if isinstance(image_input, bytes):
        mime = _get_mime_type(image_input)
        b64 = base64.b64encode(image_input).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    if isinstance(image_input, str) and image_input.startswith("data:image"):
        return image_input
    if isinstance(image_input, str):
        try:
            decoded = base64.b64decode(image_input)
            mime = _get_mime_type(decoded)
            return f"data:{mime};base64,{image_input}"
        except Exception:
            return f"data:image/jpeg;base64,{image_input}"
    raise ValueError(f"Unsupported image input type: {type(image_input)}")


# 🔥 UPGRADE V5: Dedicated prompt builders for each image category (testable)

def _build_body_prompt() -> str:
    """
    V6 UPGRADE: Modality-aware, region-restricted, user-friendly prompt.
    - Restricts analysis ONLY to the visible region in the image.
    - Explanation uses plain English (no medical jargon).
    - Explicitly forbids mentioning unrelated body regions.
    """
    return (
        "You are a careful medical image analysis assistant. "
        "Analyze the provided medical image step by step.\n\n"

        "STEP 1 — Identify the image type: 'skin', 'xray', 'document', or 'unknown'.\n"
        "STEP 2 — Identify the EXACT body region visible in the image.\n"
        "STEP 3 — Analyze ONLY what is visible in that specific region. "
        "NEVER mention organs or body parts NOT visible in the image.\n\n"

        "FOR SKIN IMAGES (analyze only the skin area shown):\n"
        "  - Describe any spots, rashes, bumps, patches in plain English.\n"
        "  - Color: red, dark, light, mixed, patchy.\n"
        "  - Distribution: which body part, how widespread.\n"
        "  - Size: small (coin-size) or larger.\n"
        "  - Surface: dry, moist, rough, smooth.\n"
        "  - Severity: mild / moderate / severe.\n"
        "  - 3-5 possible skin conditions (use: 'this may suggest...').\n\n"

        "FOR X-RAY IMAGES (analyze only the specific region in frame):\n"
        "  - Name the EXACT visible area (e.g., left knee joint, wrist bones, chest cavity).\n"
        "  - If it is a LEG/KNEE/FOOT/ANKLE xray: discuss ONLY bones and joints of that limb.\n"
        "  - If it is a CHEST xray: discuss ONLY lungs, ribs, heart shadow — nothing else.\n"
        "  - If it is a HAND/ARM/SHOULDER xray: discuss ONLY that arm region.\n"
        "  - NEVER mention or comment on regions outside the visible frame.\n\n"

        "CRITICAL RULES (all image types):\n"
        "- Use uncertainty language: 'may suggest', 'could indicate', 'appears to show'.\n"
        "- NEVER confirm a diagnosis. NEVER use 'you have'.\n"
        "- NEVER invent findings not visible in the image.\n"
        "- NEVER mention body parts or organs outside the detected region.\n"
        "- Explanation field MUST use plain, everyday English. "
        "Replace: lesion→spot/patch, erythema→redness, pruritus→itching, "
        "opacity→cloudiness, consolidation→thickening, fracture→break/crack.\n"
        "- Tone: warm and calm like a caring friend, not a clinical report.\n\n"

        "FOR DOCUMENTS: populate document_type, org_name, is_handwritten, "
        "medications_listed, patient_details_visible.\n\n"

        "Return ONLY valid JSON (no markdown, no code fences):\n"
        "{\n"
        '  "image_type": "skin | xray | document | unknown",\n'
        '  "body_region": "exact region visible, e.g. left knee, chest, lower back skin",\n'
        '  "document_type": "null or prescription | lab_report | discharge_summary | etc",\n'
        '  "org_name": "null or clinic name",\n'
        '  "is_handwritten": null or true or false,\n'
        '  "medications_listed": null or true or false,\n'
        '  "patient_details_visible": null or true or false,\n'
        '  "visual_findings": ["plain-English finding 1", "finding 2"],\n'
        '  "lesion_morphology": "null or plain-language lesion description",\n'
        '  "color_description": "null or color description",\n'
        '  "distribution": "null or body area and pattern",\n'
        '  "severity": "null | mild | moderate | severe",\n'
        '  "possible_conditions": ["condition 1", "condition 2", "condition 3"],\n'
        '  "confidence": 0.0 to 1.0,\n'
        '  "explanation": "3-5 sentence plain-English summary for a non-medical person. ONLY discuss the visible region. No jargon."\n'
        "}"
    )


# 🔥 UPGRADE V5: Granular error classification helpers

def _is_model_decommissioned_error(exc: Exception) -> bool:
    """Returns True if the Groq API error indicates a decommissioned model."""
    msg = str(exc).lower()
    return "model_decommissioned" in msg or "model is no longer supported" in msg


def _is_api_400_error(exc: Exception) -> bool:
    """Returns True if the Groq API returned a 400 Bad Request."""
    msg = str(exc).lower()
    return "400" in msg or "bad request" in msg or "invalid_request_error" in msg


async def analyze_medical_image(image_input: Any) -> Dict[str, Any]:
    """
    Analyzes an in-memory image via Groq Vision API (Asynchronously).

    # 🔥 UPGRADE V5: Single-pass unified classification.
    The prompt now handles all image types in ONE API call:
    - For documents: returns full structured metadata fields in same response.
    - Eliminates the sequential two-pass approach (P4.1 latency fix).
    - Applies VISION_API_TIMEOUT_SECONDS cap to Groq call.
    - Granular error catching: timeout, model_decommissioned, API 400.

    Args:
        image_input: Bytes, base64 data URL, or raw base64 string.

    Returns:
        Structured findings dict, or safe fallback with confidence=0 on error.
    """
    try:
        client  = _get_async_client()
        data_url = _normalize_image_to_data_url(image_input)

        # 🔥 UPGRADE V5: Single unified API call — no second round-trip for documents
        completion = await asyncio.wait_for(
            client.chat.completions.create(
                model=_MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text",      "text": _build_body_prompt()},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }],
                response_format={"type": "json_object"},
                temperature=0.0,
            ),
            timeout=VISION_API_TIMEOUT_SECONDS,
        )

        content = completion.choices[0].message.content
        if not content:
            raise ValueError("Empty response from Groq Vision API")

        return json.loads(content)

    # 🔥 UPGRADE V5: Granular error catches ─────────────────────────────────────

    except asyncio.TimeoutError:
        logger.error(
            f"[vision_classifier] Groq Vision API timed out after {VISION_API_TIMEOUT_SECONDS}s"
        )
        return _get_fallback_error("Vision API request timed out. Please retry.")

    except json.JSONDecodeError as e:
        logger.error(f"[vision_classifier] Vision API returned invalid JSON: {e}")
        return _get_fallback_error("Model returned malformed output.")

    except Exception as e:
        if _is_model_decommissioned_error(e):
            logger.error(f"[vision_classifier] Model decommissioned: {e}")
            return _get_fallback_error(
                "The vision model is currently unavailable (decommissioned). "
                "Please contact support."
            )
        if _is_api_400_error(e):
            logger.error(f"[vision_classifier] API 400 bad request: {e}")
            return _get_fallback_error(
                "Image format not accepted by the vision API. "
                "Please upload a clear JPG or PNG."
            )
        logger.error(f"[vision_classifier] Unexpected error: {e}")
        return _get_fallback_error(f"Analysis failed: {str(e)}")


def _get_fallback_error(msg: str) -> Dict[str, Any]:
    """
    # 🔥 UPGRADE V5: Returns a safe structured fallback with confidence=0
    and risk_level="unknown" so downstream nodes can gate correctly.
    """
    return {
        "image_type": "unknown",
        "visual_findings": [],
        "confidence": 0.0,
        "risk_level": "unknown",   # 🔥 UPGRADE V5: explicit sentinel for risk_evaluation_node
        "explanation": (
            f"⚠️ Image analysis could not be completed: {msg} "
            "Please upload a clear JPG or PNG and try again. "
            "This is an automated system — consult a doctor for medical advice."
        ),
    }
