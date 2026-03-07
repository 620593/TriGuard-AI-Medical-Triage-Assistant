"""
gemini_tool.py  (Version 6)
-----------------------------
Stateless client for Google Gemini API.
Package used: google-generativeai (import google.generativeai as genai)
Used exclusively by nutrition_node.
"""

import os
import google.generativeai as genai
from backend.src.logging.logger import get_logger

logger = get_logger("gemini_tool")

# Retrieve API key once
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if _GEMINI_API_KEY:
    genai.configure(api_key=_GEMINI_API_KEY)


async def call_gemini(prompt: str, model_name: str = "gemini-2.0-flash") -> str:
    """
    Calls the Gemini API asynchronously using generate_content_async.
    
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
        model = genai.GenerativeModel(model_name)
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        return response.text
    except Exception:
        logger.error("Failed to generate content from Gemini API.")
        raise RuntimeError("Gemini API error occurred.")
