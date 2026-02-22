"""
ocr_tool.py  (Version 3)
--------------------------
Extracts text from uploaded images (prescriptions, lab reports, doctor notes).

Uses pytesseract (Tesseract OCR engine) for reliable text extraction.

Anti-hallucination:
    This tool ONLY extracts text. It does not interpret, diagnose, or
    analyse the content. Interpretation is done by downstream LLaMA nodes.

Returns:
    str: Extracted text from the image. Empty string on failure.
"""

import os

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None       # type: ignore
    pytesseract = None  # type: ignore


def extract_text_from_image(image_path: str, lang: str = "eng") -> str:
    """
    Runs OCR on an image file and returns extracted text.

    Args:
        image_path: Absolute path to the image file (PNG, JPG, TIFF).
        lang: Tesseract language code (default 'eng', use 'hin' for Hindi, etc.).

    Returns:
        str: Extracted text, or empty string on failure.
    """
    if pytesseract is None or Image is None:
        print("[ocr_tool] pytesseract or Pillow not installed — skipping OCR.")
        return ""

    if not os.path.exists(image_path):
        print(f"[ocr_tool] File not found: {image_path}")
        return ""

    try:
        img = Image.open(image_path)

        # Convert to RGB if needed (handles RGBA PNGs, grayscale, etc.)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip() if text else ""

    except Exception as e:
        print(f"[ocr_tool] OCR extraction failed: {e}")
        return ""
