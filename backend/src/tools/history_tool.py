"""
history_tool.py
---------------
Provides two utility functions for persisting session state to disk.
history.json lives in the project root and acts as local session memory.
No database involvement — pure file I/O.
"""

import json
import os
from typing import Any, Dict

# Absolute path to history.json at the project root
HISTORY_FILE = os.path.join(
    os.path.dirname(__file__),   # .../src/tools/
    "..", "..",                  # up to project root
    "history.json"
)
HISTORY_FILE = os.path.abspath(HISTORY_FILE)


def load_history() -> Dict[str, Any]:
    """
    Loads the persisted session state from history.json.

    Returns:
        dict: Previously stored state, or an empty dict if file doesn't exist.
    """
    if not os.path.exists(HISTORY_FILE):
        return {}  # No prior session — start fresh

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(state: Dict[str, Any]) -> None:
    """
    Writes the current session state to history.json.

    Args:
        state (dict): The full TriageState to persist.
    """
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
