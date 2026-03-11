"""
ocr_tool.py  (Version 5 — Vision LLM Fallback)
-------------------------------------------------
Extracts text from uploaded images (prescriptions, lab reports, doctor notes).

Strategy (ordered):
    1. pytesseract (Tesseract OCR) — fast, local, no API cost.
    2. Groq Vision LLM fallback   — uses the same GROQ_API_KEY already
       configured for the pipeline. Sends the image to a multimodal
       LLaMA model with a strict "extract text only" prompt.

V5 upgrade:
    When Tesseract is not installed (common on Windows / Docker without
    the system binary), the tool transparently falls back to the Groq
    vision API so the OCR pipeline keeps working.

V4 (preserved):
    Accepts both file path (str) and raw bytes for in-memory pipelines.

Anti-hallucination:
    This tool ONLY extracts text. It does not interpret, diagnose, or
    analyse the content. Interpretation is done by downstream LLaMA nodes.

Returns:
    str: Extracted text from the image. Empty string on failure.
"""

import os
import io
import base64
import logging
from typing import Union

_logger = logging.getLogger("triguard.ocr_tool")

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore

# Tesseract is optional — if missing we fall back to vision LLM
_tesseract_available = False
try:
    import pytesseract
    # Quick probe: pytesseract.get_tesseract_version() throws if binary missing
    pytesseract.get_tesseract_version()
    _tesseract_available = True
except Exception:
    pytesseract = None  # type: ignore

# ── Groq vision LLM fallback (lazy client) ───────────────────────────────────
_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
_VISION_TIMEOUT = 30  # seconds


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


def _source_to_bytes(source: Union[str, bytes]) -> bytes:
    """Converts a file path or raw bytes to raw bytes."""
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, str):
        if not os.path.exists(source):
            raise FileNotFoundError(f"File not found: {source}")
        with open(source, "rb") as f:
            return f.read()
    raise TypeError(f"Unsupported source type: {type(source)}")


def _extract_via_vision_llm(image_bytes: bytes) -> str:
    """
    Sends the image to Groq Vision LLM with a text-extraction-only prompt.
    Returns the extracted text, or empty string on failure.
    """
    try:
        from groq import Groq
    except ImportError:
        _logger.warning("[ocr_tool] groq package not installed — cannot use vision fallback.")
        return ""

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        _logger.warning("[ocr_tool] GROQ_API_KEY not set — cannot use vision fallback.")
        return ""

    mime = _get_mime_type(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    prompt = (
        "You are a precise OCR engine. Extract ALL visible text from this "
        "medical document image exactly as written. Preserve the original "
        "layout, line breaks, headers, labels, values, dates, and numbers. "
        "Do NOT interpret, summarize, or add any commentary. "
        "Return ONLY the raw extracted text, nothing else."
    )

    try:
        client = Groq(api_key=api_key, timeout=_VISION_TIMEOUT)
        response = client.chat.completions.create(
            model=_VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
            temperature=0.0,
            max_tokens=2048,
        )
        text = response.choices[0].message.content
        return text.strip() if text else ""
    except Exception as exc:
        _logger.error(f"[ocr_tool] Vision LLM OCR failed: {exc}")
        return ""


def _extract_via_tesseract(source: Union[str, bytes], lang: str = "eng") -> str:
    """Runs local Tesseract OCR. Returns extracted text or empty string."""
    if not _tesseract_available or Image is None:
        return ""

    try:
        if isinstance(source, (bytes, bytearray)):
            img = Image.open(io.BytesIO(source))
        elif isinstance(source, str):
            if not os.path.exists(source):
                _logger.warning(f"[ocr_tool] File not found: {source}")
                return ""
            img = Image.open(source)
        else:
            return ""

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip() if text else ""
    except Exception as e:
        _logger.error(f"[ocr_tool] Tesseract OCR failed: {e}")
        return ""


def extract_text_from_image(source: Union[str, bytes], lang: str = "eng") -> str:
    """
    Runs OCR on an image and returns extracted text.

    Strategy:
      1. Try Tesseract (fast, local) if available.
      2. Fall back to Groq Vision LLM if Tesseract is missing or fails.

    Accepts either:
      - A file path string (str): opens the file from disk.
      - Raw image bytes (bytes/bytearray): opens directly from memory.

    Args:
        source: Absolute file path OR raw image bytes (PNG, JPG, TIFF, WebP, BMP).
        lang:   Tesseract language code (default 'eng').

    Returns:
        str: Extracted text, or empty string on failure.
    """
    # ── Strategy 1: Tesseract (local) ────────────────────────────────────────
    if _tesseract_available:
        text = _extract_via_tesseract(source, lang)
        if text:
            _logger.info("[ocr_tool] Text extracted via Tesseract.")
            return text

    # ── Strategy 2: Groq Vision LLM fallback ─────────────────────────────────
    _logger.info("[ocr_tool] Tesseract unavailable or empty — using Vision LLM fallback.")
    try:
        image_bytes = _source_to_bytes(source)
    except (FileNotFoundError, TypeError) as e:
        _logger.error(f"[ocr_tool] Cannot read source: {e}")
        return ""

    return _extract_via_vision_llm(image_bytes)
