"""
groq_llama_tool.py
------------------
Thin wrapper around the Groq API for LLaMA 3.1 completions.

Why it exists:
    All LLaMA calls in the pipeline go through ONE function so we can easily
    swap models or tune parameters in one place. Returns plain text only.

Input:
    prompt (str) : Full prompt string to send to LLaMA.

Returns:
    str : LLaMA's response text (stripped), or empty string on failure.
"""

import os
from groq import Groq

# LLaMA model used across all V2 nodes
_MODEL = "llama-3.1-8b-instant"

# Lazy singleton: None until first call, then reused for all subsequent calls
_client: Groq | None = None


def call_llama(prompt: str, max_tokens: int = 512) -> str:
    """
    Sends a prompt to Groq LLaMA and returns the response as plain text.

    Client is a lazy singleton: created once on the first call (after
    load_dotenv() has run), then reused for all subsequent calls to avoid
    repeated object creation overhead on a hot path.

    Args:
        prompt     (str): Full prompt string.
        max_tokens (int): Hard cap on response length.

    Returns:
        str: LLaMA response text, stripped. Empty string on error.
    """
    global _client

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        print("[groq_llama_tool] GROQ_API_KEY not set — skipping LLaMA call.")
        return ""

    # Network-safe wrapper: client init AND API call are inside try/except
    # because SSL/auth errors can occur during Groq() construction too.
    try:
        # Initialize once and cache for all future calls
        if _client is None:
            _client = Groq(api_key=api_key)

        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.2,        # Low temperature → less hallucination
        )
        return response.choices[0].message.content.strip()

    except KeyboardInterrupt:
        print("[groq_llama_tool] Request interrupted — skipping LLaMA call.")
        return ""

    except Exception as e:
        print(f"[groq_llama_tool] LLaMA call failed: {e}")
        return ""
