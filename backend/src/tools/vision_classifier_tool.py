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
from typing import Dict, Any, Optional
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
    # 🔥 UPGRADE V5 (P4.1 fix): Single unified prompt for ALL image types.
    Returns full document metadata fields when image_type=="document",
    and standard findings for skin/xray/unknown.
    This eliminates the sequential second API call for documents.
    """
    return (
        "Analyze this medical image. Categorize image_type as:"
        "'skin', 'xray', 'document', or 'unknown'.\n\n"
        "Rules:\n"
        "- Use uncertainty-based language (may, could, might).\n"
        "- NEVER confirm a diagnosis or prescribe medication.\n"
        "- If confidence is low (< 0.6), ask for a clearer image.\n"
        "- Always include: 'This is an automated analysis, not a diagnosis."  
        " Consult a doctor.'\n\n"
        "If image_type == 'document', ALSO populate these document fields:\n"
        "  document_type: one of prescription | lab_report | discharge_summary | "
        "doctor_note | insurance_form | diagnostic_report | other\n"
        "  org_name: visible clinic/hospital name, or 'not_visible'\n"
        "  is_handwritten: true if any handwritten text is visible\n"
        "  medications_listed: true if medication names/dosages visible\n"
        "  patient_details_visible: true if patient name/DOB/ID visible\n"
        "  NEVER read out or repeat patient personal details.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "image_type": "skin | xray | document | unknown",\n'
        '  "document_type": "prescription | lab_report | ... (document only, else null)",\n'
        '  "org_name": "clinic name or not_visible (document only, else null)",\n'
        '  "is_handwritten": true or false (document only, else null),\n'
        '  "medications_listed": true or false (document only, else null),\n'
        '  "patient_details_visible": true or false (document only, else null),\n'
        '  "visual_findings": ["item1", "item2"],\n'
        '  "confidence": 0.0,\n'
        '  "explanation": "Detailed summary with disclaimer..."\n'
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
