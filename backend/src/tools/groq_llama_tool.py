"""
groq_llama_tool.py  (Version 4 — Production Hardened)
------------------------------------------------------
Thin wrapper around the Groq API for LLaMA 3.1 completions.

All LLaMA calls in the pipeline go through ONE function so we can
swap models or tune parameters in a single place. Returns plain text only.

Improvements over V3:
    - Uses structured logger instead of print() for observability.
    - Thread-safe double-checked locking for client singleton.
    - Separates API-key check from client init (init only once).
"""

import logging
import os
import threading

from groq import Groq

_logger = logging.getLogger("triguard.groq_llama")

# LLaMA model used across all pipeline nodes
_MODEL = "llama-3.1-8b-instant"

# Lazy singleton — None until first call, then reused for all calls
_client: Groq | None = None
_lock = threading.Lock()


def call_llama(prompt: str, max_tokens: int = 512) -> str:
    """
    Sends a prompt to Groq LLaMA and returns the response as plain text.

    Client is a lazy singleton: created once on the first call (after
    load_dotenv() has run), then reused for all subsequent calls to avoid
    repeated object creation overhead on the hot path.

    Args:
        prompt     (str): Full prompt string.
        max_tokens (int): Hard cap on response length (tokens).

    Returns:
        str: LLaMA response text, stripped. Empty string on any error.
    """
    global _client

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        _logger.warning("GROQ_API_KEY not set — skipping LLaMA call.")
        return ""

    try:
        # Double-checked locking — safe for multhreaded asyncio.to_thread workers
        if _client is None:
            with _lock:
                if _client is None:
                    _client = Groq(api_key=api_key)

        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.2,   # Low temperature → less hallucination
        )
        return response.choices[0].message.content.strip()

    except KeyboardInterrupt:
        _logger.warning("LLaMA call interrupted by KeyboardInterrupt.")
        return ""

    except Exception as exc:
        _logger.error(f"LLaMA call failed: {exc}")
        return ""
