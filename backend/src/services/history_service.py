"""
history_service.py  (Version 1 — Async-Safe MongoDB History Retrieval)
-----------------------------------------------------------------------
Fetches and formats user past health reports from MongoDB.

Features:
  - Fully async using Motor's AsyncIOMotorClient (no blocking calls).
  - Handles "give me my past issues" intent with structured history response.
  - Fallback message when no history exists.
  - Integration with response_formatter for display.
  - Properly isolated from sync contexts (caller must await).

Contract:
  - Input:  user_id, optional keyword trigger (e.g., "past issues")
  - Output: List[dict] of raw reports (formatted by response_formatter)
"""

from typing import List, Optional
from backend.src.tools.mongodb_tool import _get_db
from backend.src.logging.logger import get_logger, log_event
from backend.src.services.response_formatter import build_history_response

logger = get_logger("history_service")

# Keywords that signal the user wants their history
_HISTORY_TRIGGER_PHRASES = frozenset({
    "past issue", "past issues", "previous issue", "my history",
    "health history", "past health", "past problems", "what did i have",
    "my condition", "earlier symptoms", "my records", "past records",
    "prior history", "past consultation", "what was wrong before",
    "last time", "previous symptoms", "before this", "my old reports",
})


def is_history_request(user_input: str) -> bool:
    """
    Returns True if the user's message is asking about their health history.

    Args:
        user_input: Raw user message text.

    Returns:
        bool
    """
    if not user_input:
        return False
    lower = user_input.lower()
    return any(phrase in lower for phrase in _HISTORY_TRIGGER_PHRASES)


async def fetch_user_history(user_id: str, limit: int = 5) -> List[dict]:
    """
    Fetches the most recent health reports for a user from MongoDB.

    Args:
        user_id: The user's unique identifier.
        limit:   Max reports to fetch (default 5).

    Returns:
        List of sanitized report dicts, newest first.
    """
    if not user_id or user_id == "anonymous":
        log_event(logger, "history_fetch_skipped", reason="anonymous_user")
        return []

    try:
        db = _get_db()
        cursor = (
            db.reports
            .find({"report.user_id": str(user_id)})
            .sort("created_at", -1)
            .limit(limit)
        )

        reports = []
        async for doc in cursor:
            report = doc.get("report", {})
            sanitized = {
                "created_at": str(doc.get("created_at", "Unknown")),
                "risk_level":       report.get("risk_level", "unknown"),
                "symptoms":         report.get("symptoms", []),
                "clinical_summary": (
                    report.get("clinical_summary")
                    or report.get("summary")
                    or (report.get("llm_output", {}) or {}).get("clinical_summary", "")
                    or "No summary available."
                ),
                "urgency":    report.get("urgency", "routine"),
                "intent":     report.get("intent", "medical_text"),
            }
            reports.append(sanitized)

        log_event(logger, "history_fetched",
                  user_id=user_id,
                  count=len(reports))
        return reports

    except Exception as e:
        log_event(logger, "history_fetch_error", user_id=user_id, error=str(e))
        return []


async def get_history_response(user_id: str) -> str:
    """
    Full pipeline: fetch user history → format into chatbot-style response.

    Args:
        user_id: User's unique ID.

    Returns:
        Formatted string response ready to send to user.
    """
    reports = await fetch_user_history(user_id, limit=5)
    return build_history_response(reports)
