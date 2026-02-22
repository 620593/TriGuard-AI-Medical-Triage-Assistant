"""
tavily_tool.py  (Version 2)
---------------------------
Queries Tavily for grounded medical information.
Uses a structured, symptom-aware query for better relevance.

Anti-hallucination rules:
  - Only returns actual Tavily results.
  - If API fails or returns nothing → returns [].
  - Caller decides what to do with empty results.

Input:
    symptoms (list[str]): Extracted symptom keywords.

Returns:
    list[str]: Up to 3 medical summaries. Empty list on failure.
"""

import os
from tavily import TavilyClient
from typing import List

# Lazy singleton: None until first call, then reused for all subsequent calls
_client: TavilyClient | None = None


def search_medical_info(symptoms: List[str]) -> List[str]:
    """
    Retrieves medical information from Tavily for the given symptom list.

    Client is a lazy singleton: created once on the first call (after
    load_dotenv() has run), then reused to avoid repeated object creation.

    Args:
        symptoms (list[str]): Symptom keywords to search.

    Returns:
        list[str]: Up to 3 medical summaries, or [] on failure/empty results.
    """
    global _client

    if not symptoms:
        return []

    # Lazy init: reads TAVILY_API_KEY at call-time (after load_dotenv)
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        print("[tavily_tool] TAVILY_API_KEY not set — skipping retrieval.")
        return []

    # Network-safe wrapper to prevent API failure from crashing graph.
    # Client init AND search are both inside try/except because SSL
    # handshake errors can occur during TavilyClient() construction.
    try:
        # Initialize once and cache for all future calls
        if _client is None:
            _client = TavilyClient(api_key=api_key)

        # Build a specific, medically-framed query
        symptom_str = ", ".join(symptoms)
        query = f"symptoms and causes of: {symptom_str} — medical information"

        response = _client.search(
            query=query,
            search_depth="advanced",
            max_results=3,
            include_answer=True,
        )

        results = []

        # Include Tavily's synthesised answer if available
        if response.get("answer"):
            results.append(response["answer"])

        # Add individual result snippets up to the cap
        for item in response.get("results", []):
            content = item.get("content", "").strip()
            if content and len(results) < 3:
                results.append(content)

        return results

    except KeyboardInterrupt:
        # SSL handshake timeouts surface as KeyboardInterrupt on Windows.
        # Catch it here so Ctrl+C during a slow API call doesn't kill the
        # entire graph — the pipeline falls back to no-retrieval mode.
        print("[tavily_tool] Request interrupted (SSL/timeout) — skipping retrieval.")
        return []

    except Exception as e:
        # Catches: requests.ConnectionError, Timeout, SSLError, HTTP errors,
        # Tavily SDK errors, and any other unexpected failures.
        print(f"[tavily_tool] Search failed: {e}")
        return []
