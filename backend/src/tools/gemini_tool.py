"""
gemini_tool.py  (Version 7)
-----------------------------
Stateless client for Google Gemini API.
Package used: google-genai (from google import genai)
Used exclusively by nutrition_node.
"""

import os
from typing import Any
from google import genai
from google.genai import types
from backend.src.logging.logger import get_logger

logger = get_logger("gemini_tool")

# Retrieve API key once
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def _extract_text(response: Any) -> str:
    """Returns best-effort text output from google-genai response."""
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    return str(response)


async def call_gemini(prompt: str, model_name: str = "gemini-2.0-flash") -> str:
    """
    Calls the Gemini API asynchronously using google-genai.
    
    Args:
        prompt: The full prompt string.
        model_name: The target Gemini model.
        
    Returns:
        The generated text from the model.
        
    Raises:
        ValueError: If GEMINI_API_KEY is missing.
        RuntimeError: If the API call fails.
    """
    if not _GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not found.")
        raise ValueError("GEMINI_API_KEY environment variable is not set.")

    try:
        client = genai.Client(api_key=_GEMINI_API_KEY)
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )
        return _extract_text(response)
    except Exception:
        logger.error("Failed to generate content from Gemini API.")
        raise RuntimeError("Gemini API error occurred.")
