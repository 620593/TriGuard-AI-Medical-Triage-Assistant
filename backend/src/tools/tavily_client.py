"""
tavily_client.py  (Version 6 — tools/)
----------------------------------------
Stateless Tavily medical web search client.

Rules:
    - NEVER modifies state.
    - Pure function: accepts query string, returns results dict.
    - Reads env vars at call time.
"""

import os
from typing import List


def search_medical(
    query: str,
    max_results: int = 5,
    search_depth: str = "advanced",
) -> dict:
    """
    Performs a Tavily web search scoped to medical content.

    Args:
        query:        Search query string.
        max_results:  Maximum number of results to return (default 5).
        search_depth: 'basic' or 'advanced' (default 'advanced').

    Returns:
        dict with keys: {'results': List[str], 'success': bool, 'error': str | None}
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return {"results": [], "success": False, "error": "TAVILY_API_KEY not set"}

    if not query or not query.strip():
        return {"results": [], "success": False, "error": "Empty query"}

    try:
        from tavily import TavilyClient  # type: ignore[import]

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query.strip()[:512],
            search_depth=search_depth,
            max_results=max_results,
            include_domains=["pubmed.ncbi.nlm.nih.gov", "mayoclinic.org",
                             "webmd.com", "medlineplus.gov", "who.int",
                             "cdc.gov", "nhs.uk"],
        )
        results: List[str] = [
            r.get("content", "")
            for r in response.get("results", [])
            if r.get("content")
        ]
        return {"results": results[:max_results], "success": True, "error": None}

    except Exception as exc:
        return {"results": [], "success": False, "error": str(exc)}
