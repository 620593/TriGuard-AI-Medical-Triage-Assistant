"""
nutrition_image_tool.py  (Version 4 — Production Hardened)
-----------------------------------------------------------
Generates dietary suggestions and optional meal images.

For image generation:
    Uses HuggingFace's Stable Diffusion inference API (free tier).
    Falls back to text-only advice if image generation fails or
    HF_API_TOKEN is not configured.

Anti-hallucination:
    Dietary advice is generic and evidence-based (not personalized prescriptions).
    Always includes a disclaimer about consulting a dietitian.

V4 changes:
    - Removed module-level os.makedirs (directories created by main.py lifespan).
    - Replaced print() with structured logger.
    - Explicit requests import guard unchanged.
"""

import logging
import os
import time
import uuid
from pathlib import Path

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]

from backend.src.tools.groq_llama_tool import call_llama

_logger = logging.getLogger("triguard.nutrition_image")

# Output directory — anchored to project root, not CWD
_PROJECT_ROOT  = Path(__file__).resolve().parent.parent.parent
_NUTRITION_DIR = str(_PROJECT_ROOT / "nutrition_images")

_MAX_AGE_SECONDS = 3600  # 1 hour


def _cleanup_old_files() -> None:
    """Deletes nutrition image files older than _MAX_AGE_SECONDS."""
    if not os.path.exists(_NUTRITION_DIR):
        return
    now = time.time()
    for filename in os.listdir(_NUTRITION_DIR):
        filepath = os.path.join(_NUTRITION_DIR, filename)
        if not os.path.isfile(filepath):
            continue
        try:
            if now - os.path.getmtime(filepath) > _MAX_AGE_SECONDS:
                os.remove(filepath)
        except OSError as exc:
            _logger.warning(f"Nutrition image cleanup failed for {filename}: {exc}")


def generate_nutrition_advice(symptoms: list, risk_level: str) -> dict:
    """
    Generates dietary suggestions based on symptoms and risk level.
    Only called for LOW or MODERATE risk levels.

    Args:
        symptoms:   Patient's symptom list.
        risk_level: Current risk assessment.

    Returns:
        dict: {"advice": str, "image_url": str}
              image_url is a filename string (not a full URL).
    """
    symptom_str = ", ".join(symptoms) if symptoms else "general wellness"

    prompt = (
        "You are a nutrition advisor. Based on these symptoms, suggest 3-5 "
        "dietary recommendations. Do NOT prescribe medication or supplements. "
        "Keep it to general, evidence-based dietary advice.\n\n"
        f"Symptoms: {symptom_str}\n"
        f"Risk level: {risk_level}\n\n"
        "Format:\n"
        "1. **[Short title]**: [one-sentence explanation]\n"
        "2. **[Short title]**: [one-sentence explanation]\n"
        "3. **[Short title]**: [one-sentence explanation]\n\n"
        "End with: Consult a registered dietitian for personalized advice."
    )

    advice = call_llama(prompt, max_tokens=300)
    if not advice:
        advice = (
            "General dietary recommendations:\n"
            "1. **Stay hydrated**: Drink plenty of water throughout the day.\n"
            "2. **Eat balanced meals**: Include fruits, vegetables, and whole grains.\n"
            "3. **Avoid trigger foods**: Steer clear of processed foods and excess sugar.\n\n"
            "Consult a registered dietitian for personalized advice."
        )

    # Attempt meal image generation via HuggingFace API
    image_filename = _generate_meal_image(symptom_str)

    return {"advice": advice, "image_url": image_filename}


def _generate_meal_image(context: str) -> str:
    """
    Generates a healthy meal image using HuggingFace Stable Diffusion API.

    Returns:
        str: Filename of the saved image. Empty string on failure or missing token.
    """
    hf_token = os.environ.get("HF_API_TOKEN", "")
    if not hf_token or _requests is None:
        return ""

    try:
        api_url = (
            "https://router.huggingface.co/models/"
            "stabilityai/stable-diffusion-xl-base-1.0"
        )
        headers = {"Authorization": f"Bearer {hf_token}"}
        prompt_text = (
            f"A beautiful, appetizing photograph of a healthy balanced meal "
            f"suitable for someone with {context}. Top-down view, natural lighting, "
            f"professional food photography, vibrant colors."
        )

        response = _requests.post(
            api_url,
            headers=headers,
            json={"inputs": prompt_text},
            timeout=30,
        )

        if response.status_code == 200:
            # Ensure directory exists defensively
            os.makedirs(_NUTRITION_DIR, exist_ok=True)
            _cleanup_old_files()

            filename = f"meal_{uuid.uuid4().hex[:8]}.png"
            filepath = os.path.join(_NUTRITION_DIR, filename)
            with open(filepath, "wb") as fout:
                fout.write(response.content)
            return filename

        _logger.warning(f"HuggingFace returned HTTP {response.status_code} for meal image.")
        return ""

    except Exception as exc:
        _logger.error(f"Meal image generation failed: {exc}")
        return ""
