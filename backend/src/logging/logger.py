"""
logger.py  (Version 3)
-----------------------
Structured JSON logging for the entire pipeline.

Why JSON:
    Machine-parseable logs enable easy integration with log aggregation
    tools (ELK, Datadog, CloudWatch) and observability platforms.

PHI Safety:
    In production mode (TRIGUARD_ENV=production), user messages and
    symptoms are redacted from log output to protect health information.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any


# ── Configuration ──────────────────────────────────────────────────────────────
_ENV = os.environ.get("TRIGUARD_ENV", "development")   # 'development' | 'production'
_LOG_LEVEL = os.environ.get("TRIGUARD_LOG_LEVEL", "INFO").upper()

# Fields that contain PHI and must be redacted in production
_PHI_FIELDS = {"user_input", "symptoms", "messages", "extracted_text", "patient_context"}


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }

        # Merge extra structured data if present
        extra: dict = getattr(record, "extra_data", {})
        if extra:
            # PHI redaction in production
            if _ENV == "production":
                for key in _PHI_FIELDS:
                    if key in extra:
                        extra[key] = "[REDACTED]"
            log_entry["data"] = extra

        return json.dumps(log_entry, default=str)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger with JSON output.

    Args:
        name: Module name (e.g. 'risk_tool', 'triage_api').

    Returns:
        logging.Logger: Configured JSON logger.
    """
    logger = logging.getLogger(f"triguard.{name}")

    # Avoid adding duplicate handlers on repeated calls
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))

    return logger


def log_event(logger: logging.Logger, event: str, **kwargs: Any) -> None:
    """
    Logs a structured event with arbitrary key-value data.

    Args:
        logger: The logger instance.
        event:  Short event name (e.g. 'symptom_extracted', 'risk_scored').
        **kwargs: Any structured data to attach to the log entry.
    """
    record = logger.makeRecord(
        name=logger.name,
        level=logging.INFO,
        fn="",
        lno=0,
        msg=event,
        args=(),
        exc_info=None,
    )
    record.extra_data = kwargs  # type: ignore[attr-defined]
    logger.handle(record)


# ── Observability: latency tracking ───────────────────────────────────────────

class LatencyTracker:
    """
    Simple context manager for tracking operation duration.

    Usage:
        with LatencyTracker("tavily_search") as t:
            results = search(...)
        print(t.duration_ms)
    """

    def __init__(self, operation: str):
        self.operation = operation
        self.start = 0.0
        self.duration_ms = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.duration_ms = round((time.perf_counter() - self.start) * 1000, 2)
