"""
ocr_tool.py  (Version 4)
--------------------------
Extracts text from uploaded images (prescriptions, lab reports, doctor notes).

Uses pytesseract (Tesseract OCR engine) for reliable text extraction.

V4 fix:
    Previous signature only accepted a file path string.
    ocr_scan_node passes raw bytes when image_input is in-memory (no temp file).
    Added overloaded input: accepts both a file path (str) OR raw bytes.
    This fixes the "ocr_empty_result: source=bytes" bug that caused the OCR
    pipeline to return empty text, sending loose-motion reports through
    the text pipeline with zero symptoms → LLM hallucinated "cold and fever".

Anti-hallucination:
    This tool ONLY extracts text. It does not interpret, diagnose, or
    analyse the content. Interpretation is done by downstream LLaMA nodes.

Returns:
    str: Extracted text from the image. Empty string on failure.
"""

import os
import io
from typing import Union

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None        # type: ignore
    pytesseract = None  # type: ignore


def extract_text_from_image(source: Union[str, bytes], lang: str = "eng") -> str:
    """
    Runs OCR on an image and returns extracted text.

    Accepts either:
      - A file path string (str): opens the file from disk.
      - Raw image bytes (bytes/bytearray): opens directly from memory.
        This is the V4 fix — in-memory API pipelines never write a temp file.

    Args:
        source: Absolute file path OR raw image bytes (PNG, JPG, TIFF, WebP, BMP).
        lang:   Tesseract language code (default 'eng').

    Returns:
        str: Extracted text, or empty string on failure.
    """
    if pytesseract is None or Image is None:
        print("[ocr_tool] pytesseract or Pillow not installed — skipping OCR.")
        return ""

    try:
        # ── V4 Fix: handle both file paths and raw bytes ─────────────────────
        if isinstance(source, (bytes, bytearray)):
            # In-memory path: open directly from bytes buffer
            img = Image.open(io.BytesIO(source))
        elif isinstance(source, str):
            # File path: validate existence first
            if not os.path.exists(source):
                print(f"[ocr_tool] File not found: {source}")
                return ""
            img = Image.open(source)
        else:
            print(f"[ocr_tool] Unsupported source type: {type(source)}")
            return ""

        # Convert to RGB/L if needed (handles RGBA PNGs, grayscale, palette, etc.)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip() if text else ""

    except Exception as e:
        print(f"[ocr_tool] OCR extraction failed: {e}")
        return ""
