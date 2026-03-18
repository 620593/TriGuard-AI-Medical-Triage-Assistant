"""
xray_model_tool.py
------------------
X-ray abnormality screening using Groq Vision API.

Returns:
    dict: {"findings": str, "confidence": float, "raw_labels": list}
"""

import asyncio
import base64
import json
import os
import re
import threading
from typing import Any, Dict, List

from groq import AsyncGroq

from backend.src.logging.logger import get_logger

logger = get_logger("xray_model_tool")

_MODEL = os.getenv("XRAY_GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

_SYSTEM_PROMPT = (
    "You are a radiology AI assistant performing preliminary X-ray screening.\n"
    "Analyze the provided X-ray image and identify visible abnormalities.\n"
    "You must respond ONLY with a valid JSON object — no explanation, no markdown."
)

_USER_PROMPT = (
    "Analyze this X-ray image. Identify the body part and any visible abnormalities.\n\n"
    "Respond with ONLY this JSON structure:\n"
    "{\n"
    "  \"body_part\": \"chest | spine | leg | arm | hand | foot | skull | pelvis | unknown\",\n"
    "  \"findings\": [\"finding1\", \"finding2\"],\n"
    "  \"impression\": \"one sentence clinical impression\",\n"
    "  \"confidence\": 0.0 to 1.0,\n"
    "  \"normal\": true or false\n"
    "}\n\n"
    "If no abnormality is detected, set normal=true and findings=[\"No acute findings\"].\n"
    "If image quality is poor or unclear, set confidence below 0.5 and note it in findings."
)

_PARSE_FALLBACK = {
    "body_part": "unknown",
    "findings": ["Analysis failed"],
    "impression": "Could not parse X-ray findings",
    "confidence": 0.0,
    "normal": False,
}

_async_client: AsyncGroq | None = None

def _get_async_client() -> AsyncGroq:
    global _async_client
    if _async_client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not set.")
        _async_client = AsyncGroq(api_key=api_key)
    return _async_client


def _strip_markdown_fences(content: str) -> str:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\\s*```$", "", text)
    return text.strip()


def _safe_parse_json(content: str) -> Dict[str, Any]:
    cleaned = _strip_markdown_fences(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return dict(_PARSE_FALLBACK)
    if not isinstance(parsed, dict):
        return dict(_PARSE_FALLBACK)
    return parsed


async def _call_groq_xray(image_bytes: bytes) -> Dict[str, Any]:
    client = _get_async_client()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    messages = [
        {
            "role": "system",
            "content": _SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}"
                    }
                },
                {
                    "type": "text",
                    "text": _USER_PROMPT
                }
            ]
        }
    ]

    response = await client.chat.completions.create(
        model=_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=400,
    )

    content = response.choices[0].message.content if response.choices else ""
    if not content:
        return dict(_PARSE_FALLBACK)
    return _safe_parse_json(content)


def _run_coroutine_sync(coro: Any) -> Dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: Dict[str, Any] = dict(_PARSE_FALLBACK)
    error: dict[str, Exception] = {}

    def _worker() -> None:
        try:
            result.update(asyncio.run(coro))
        except Exception as exc:
            error["exc"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()

    if "exc" in error:
        raise error["exc"]
    return result


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, score))


def _normalize_xray_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    body_part = str(payload.get("body_part", "unknown")).strip().lower() or "unknown"
    findings_raw = payload.get("findings", [])
    if not isinstance(findings_raw, list):
        findings_raw = []

    findings = [str(item).strip() for item in findings_raw if str(item).strip()]
    if not findings:
        findings = ["Analysis failed"]

    impression = str(payload.get("impression", "Could not parse X-ray findings")).strip()
    if not impression:
        impression = "Could not parse X-ray findings"

    confidence = _to_float(payload.get("confidence", 0.0), 0.0)
    normal = bool(payload.get("normal", False))

    labels = list(findings)

    raw_labels = [{"label": label, "score": round(confidence, 3)} for label in labels[:3]]
    findings_text = (
        f"Body part: {body_part}. "
        f"Impression: {impression}. "
        f"Findings: {', '.join(findings)}."
    )
    findings_text += (
        "\n\nWARNING: This is an AI-assisted screening tool. "
        "These findings must be reviewed by a qualified radiologist. "
        "Do not use this as a definitive diagnosis."
    )

    return {
        "body_part": body_part,
        "findings_list": findings,
        "impression": impression,
        "normal": normal,
        "findings": findings_text,
        "confidence": round(confidence, 3),
        "raw_labels": raw_labels,
    }


def analyze_xray(image_bytes: bytes) -> dict:
    """
    Classifies a chest/bone X-ray image against common abnormality labels.

    Accepts raw image bytes (JPEG, PNG, WebP, BMP, TIFF, GIF) directly
    from the in-memory upload pipeline — no temp file required.

    Args:
        image_bytes: Raw bytes of the X-ray image file.

    Returns:
        dict: {
            "findings": str (human-readable summary),
            "confidence": float (top prediction confidence),
            "raw_labels": list (top 3 predictions with scores)
        }
    """
    empty_result = {
        "findings": "Unable to analyze X-ray image.",
        "confidence": 0.0,
        "raw_labels": [],
    }

    if not image_bytes or not isinstance(image_bytes, (bytes, bytearray)):
        logger.warning("No image bytes provided")
        return empty_result

    try:
        parsed = _run_coroutine_sync(_call_groq_xray(bytes(image_bytes)))
        result = _normalize_xray_payload(parsed)

        logger.info(json.dumps({
            "model": "groq-vision",
            "body_part": result.get("body_part", "unknown"),
            "findings_count": len(result.get("findings_list", [])),
            "confidence": result.get("confidence", 0.0),
        }))

        return result

    except Exception as e:
        logger.error("X-ray analysis failed: %s", e)
        return empty_result
