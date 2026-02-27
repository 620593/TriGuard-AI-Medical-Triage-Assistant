"""
history_tool.py
---------------
Provides two utility functions for persisting session state to disk.
history.json lives in the project root and acts as local session memory.
No database involvement — pure file I/O.

V3 hardening:
    - load_history() now catches any JSON / IO error and returns {} instead of crashing.
    - save_history() cleans non-serialisable values before writing (belt-and-suspenders
      safety in case save_history_node misses something).
    - Atomic write: writes to a temp file then renames, preventing partial writes from
      corrupting history.json if the process is killed mid-write.
"""

import json
import os
import tempfile
from typing import Any, Dict

# Absolute path to history.json at the project root
HISTORY_FILE = os.path.join(
    os.path.dirname(__file__),   # .../src/tools/
    "..", "..",                  # up to project root
    "history.json"
)
HISTORY_FILE = os.path.abspath(HISTORY_FILE)

# Fields that must never be serialised (raw bytes, in-memory objects, transient flags).
# This set is the last-resort safety net inside save_history(); the primary stripping
# happens in save_history_node._STRIP_FIELDS which must remain the single source of truth.
# Both sets must always be supersets of each other's intent — if a field is added to
# save_history_node._STRIP_FIELDS, add it here too for defence-in-depth.
_NON_SERIALISABLE_FIELDS = frozenset({
    "image_input",        # raw bytes — never serialisable
    "audio_input",        # raw bytes — never serialisable
    "_mid_session",       # in-memory pipeline control flag
    "image_type_hint",    # in-memory routing hint
    "force_accepted",     # transient judge retry flag
    "regeneration_count", # resets to 0 each new turn
    "vision_findings",    # may contain non-serialisable objects; re-derived each turn
})


def _make_serialisable(obj: Any) -> Any:
    """
    Recursively converts non-JSON-serialisable values to safe placeholders.
    Used as a last-resort safety net before json.dump().
    """
    if isinstance(obj, bytes):
        return None          # Never serialise raw bytes to disk
    if isinstance(obj, dict):
        return {k: _make_serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serialisable(i) for i in obj]
    # Primitives (str, int, float, bool, None) are safe
    return obj


def load_history() -> Dict[str, Any]:
    """
    Loads the persisted session state from history.json.

    Returns:
        dict: Previously stored state, or an empty dict if the file doesn't
              exist, is empty, or contains malformed / corrupt JSON.
              Never raises — always returns a safe fallback.
    """
    if not os.path.exists(HISTORY_FILE):
        return {}  # No prior session — start fresh

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return {}          # Empty file — treat as no-history
        return json.loads(content)
    except (json.JSONDecodeError, ValueError, OSError, UnicodeDecodeError) as exc:
        # Log without crashing — return an empty session so the app keeps working
        print(f"[history_tool] WARNING: Could not load history.json ({exc}). "
              "Starting with a fresh session.")
        # Attempt to reset the corrupt file so it doesn't keep failing
        _reset_history()
        return {}


def save_history(state: Dict[str, Any]) -> None:
    """
    Writes the current session state to history.json atomically.

    Uses a temp file + rename to prevent creating a corrupt file if
    the process is interrupted during writing.

    Args:
        state (dict): The full TriageState to persist.
    """
    # Strip fields that cannot / should not be serialised
    payload = {
        k: v for k, v in state.items()
        if k not in _NON_SERIALISABLE_FIELDS
    }

    # Belt-and-suspenders: recursively clean any remaining non-serialisable values
    payload = _make_serialisable(payload)

    # Atomic write: write to a temp file in the same directory, then rename
    dir_name = os.path.dirname(HISTORY_FILE)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, HISTORY_FILE)   # Atomic on POSIX; best-effort on Windows
        except Exception:
            # Clean up the temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except (OSError, TypeError, ValueError) as exc:
        print(f"[history_tool] WARNING: Failed to save history.json: {exc}")


def _reset_history() -> None:
    """Overwrites history.json with a minimal valid empty state."""
    empty = {
        "messages": [],
        "symptoms": [],
        "followup_count": 0,
        "risk_level": "low",
        "risk_score": 0.0,
        "risk_confidence": 0.0,
        "session_id": "",
        "user_id": "anonymous",
        "language": "en",
    }
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(empty, f, indent=2)
    except OSError:
        pass  # If we can't write, at least don't crash
