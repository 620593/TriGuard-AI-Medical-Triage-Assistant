"""
output_parser.py  (Version 2 - Single-pass optimised)
------------------------------------------------------
Parses structured LLaMA triage responses into a typed dictionary
that the API can return directly to the frontend.

Expected LLaMA response format (set in llm_brain_node prompt):

    SUMMARY: <1-2 sentence summary>
    RISK_LEVEL: LOW | MODERATE | HIGH | CRITICAL
    RISK_SCORE: <float>/10
    ACTION: <what to do next>
    RED_FLAGS: <when to call emergency services>
    DIETARY: <bullet list of diet tips>   (optional)
    DISCLAIMER: <disclaimer text>

V2 optimisation:
    - Single-pass line-by-line parsing instead of up to 28 regex searches.
    - Section header matched with a pre-built lookup dict (O(1) per line).
    - Falls back gracefully to raw text rendering when sections not found.
"""

import re
from typing import TypedDict, Optional


class ParsedResponse(TypedDict, total=False):
    summary:        str          # Patient concern summary
    risk_level:     str          # low | moderate | high | critical
    risk_score:     str          # "2.0/10" style string
    action:         str          # What to do right now
    red_flags:      str          # Warning signs to watch for
    dietary:        str          # Nutrition advice (optional)
    disclaimer:     str          # Mandatory disclaimer
    raw:            str          # Full original text (fallback)
    is_structured:  bool         # True if parser found key sections


# Canonical names for section keys — used in the output dict and lookup
_KNOWN_SECTIONS = {
    "SUMMARY",
    "RISK_LEVEL",
    "RISK_SCORE",
    "ACTION",
    "RED_FLAGS",
    "DIETARY",
    "DISCLAIMER",
}

# Aliases: alternate header spellings → canonical key
_ALIASES: dict[str, str] = {
    "SUGGESTED_ACTION":           "ACTION",
    "SUGGESTED ACTION":           "ACTION",
    "WHEN TO SEEK IMMEDIATE HELP": "RED_FLAGS",
    "WHEN TO SEEK HELP":          "RED_FLAGS",
    "RED FLAGS":                  "RED_FLAGS",
    "RED_FLAG":                   "RED_FLAGS",
    "DIETARY SUGGESTIONS":        "DIETARY",
    "DIETARY ADVICE":             "DIETARY",
    "DIET":                       "DIETARY",
    "NUTRITION":                  "DIETARY",
    "RISK LEVEL":                 "RISK_LEVEL",
    "RISK SCORE":                 "RISK_SCORE",
}

# Pre-compiled: match "KEY:" at start of a line (strip leading emoji/whitespace)
_HEADER_RE = re.compile(
    r"^\s*(?:[^\w]*)?"           # optional leading emoji
    r"([A-Z][A-Z0-9 _]+?)"      # header word(s)
    r"\s*:\s*(.*)$",             # colon + rest of line
    re.IGNORECASE,
)

# Score pattern for inline extraction
_SCORE_RE = re.compile(r"([\d.]+)\s*/\s*10")


def _canonical(header: str) -> Optional[str]:
    """Map a matched header string to its canonical key, or None."""
    up = header.strip().upper()
    if up in _KNOWN_SECTIONS:
        return up.lower()
    alias = _ALIASES.get(up)
    return alias.lower() if alias else None


def parse_response(raw_text: str) -> ParsedResponse:
    """
    Single-pass parser: splits the LLM output into labelled sections.

    The parser iterates once through the lines, detecting section headers
    and accumulating their content into the result dict.  Time complexity
    is O(n) where n is the number of output lines (typically < 20).

    Args:
        raw_text: The full response string from llm_brain_node.

    Returns:
        ParsedResponse dict with is_structured=True when key sections found.
    """
    if not raw_text:
        return {"raw": "", "is_structured": False}

    result: dict = {"raw": raw_text, "is_structured": False}

    current_key: Optional[str] = None
    current_lines: list[str] = []

    def _flush():
        if current_key and current_lines:
            result[current_key] = " ".join(current_lines).strip()

    for line in raw_text.splitlines():
        m = _HEADER_RE.match(line)
        if m:
            key = _canonical(m.group(1))
            if key:
                _flush()
                current_key = key
                rest = m.group(2).strip()
                current_lines = [rest] if rest else []
                continue

        # Continuation of current section
        if current_key:
            stripped = line.strip()
            if stripped:
                current_lines.append(stripped)

    _flush()  # Save the last section

    # Handle emergency alert blocks (no sections, starts with 🚨)
    if "🚨" in raw_text and not result.get("summary"):
        result["is_structured"] = False
        result["risk_level"] = "critical"
        return result

    # Normalise risk_level to lowercase and strip score notation
    if result.get("risk_level"):
        rl = re.sub(r"\s*\(.*?\)", "", result["risk_level"]).strip().lower()
        result["risk_level"] = rl

    # Extract risk_score from inline notation if missing
    if not result.get("risk_score"):
        sm = _SCORE_RE.search(raw_text)
        if sm:
            result["risk_score"] = f"{sm.group(1)}/10"
    else:
        # clean up the score field (may already contain "2.0/10")
        sm = _SCORE_RE.search(result["risk_score"])
        if sm:
            result["risk_score"] = f"{sm.group(1)}/10"

    # Structured if the two most critical sections are present
    result["is_structured"] = bool(
        result.get("summary") and result.get("action")
    )

    return result
