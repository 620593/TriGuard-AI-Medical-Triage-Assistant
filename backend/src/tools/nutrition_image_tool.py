"""
nutrition_image_tool.py  (Version 3)
--------------------------------------
Generates dietary suggestions and optional meal images.

For image generation:
    Uses HuggingFace's Stable Diffusion inference API (free tier).
    Falls back to text-only advice if image generation fails.

Anti-hallucination:
    Dietary advice is generic and evidence-based (not personalized prescriptions).
    Always includes a disclaimer about consulting a dietitian.
"""

import os

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore

from backend.src.tools.groq_llama_tool import call_llama


def generate_nutrition_advice(symptoms: list, risk_level: str) -> dict:
    """
    Generates dietary suggestions based on symptoms and risk level.
    Only called for LOW or MODERATE risk levels.

    Args:
        symptoms: Patient's symptom list.
        risk_level: Current risk assessment.

    Returns:
        dict: {"advice": str, "image_url": str}
    """
    symptom_str = ", ".join(symptoms) if symptoms else "general wellness"

    prompt = (
        "You are a nutrition advisor. Based on these symptoms, suggest 3-5 "
        "dietary recommendations. Do NOT prescribe medication or supplements. "
        "Keep it to general, evidence-based dietary advice.\n\n"
        f"Symptoms: {symptom_str}\n"
        f"Risk level: {risk_level}\n\n"
        "Format:\n"
        "1. [food/diet suggestion]\n"
        "2. [food/diet suggestion]\n"
        "3. [food/diet suggestion]\n\n"
        "End with: Consult a registered dietitian for personalized advice."
    )

    advice = call_llama(prompt, max_tokens=300)
    if not advice:
        advice = (
            "General dietary recommendations:\n"
            "1. Stay well hydrated — drink plenty of water.\n"
            "2. Eat balanced meals with fruits and vegetables.\n"
            "3. Avoid processed foods and excess sugar.\n\n"
            "Consult a registered dietitian for personalized advice."
        )

    # Attempt meal image generation via HuggingFace API
    image_url = _generate_meal_image(symptom_str)

    return {"advice": advice, "image_url": image_url}


def _generate_meal_image(context: str) -> str:
    """
    Generates a healthy meal image using HuggingFace Stable Diffusion API.

    Returns:
        str: URL or base64 of the generated image. Empty string on failure.
    """
    hf_token = os.environ.get("HF_API_TOKEN", "")
    if not hf_token or _requests is None:
        return ""

    try:
        api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
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
            # Save image to disk — anchored to project root (not CWD)
            _project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            img_dir = os.path.join(_project_root, "nutrition_images")
            os.makedirs(img_dir, exist_ok=True)

            import uuid
            filepath = os.path.join(img_dir, f"meal_{uuid.uuid4().hex[:8]}.png")
            with open(filepath, "wb") as f:
                f.write(response.content)
            return filepath

        return ""

    except Exception as e:
        print(f"[nutrition_image_tool] Image generation failed: {e}")
        return ""
