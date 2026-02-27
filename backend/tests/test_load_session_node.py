"""
test_load_session_node.py
--------------------------
Tests for load_session_node: new session, existing session, mid-session pass-through.
"""

import pytest
from unittest.mock import AsyncMock, patch
from backend.tests.helpers import make_state


# --- Helper to call async node synchronously in tests ---
import asyncio

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── New session (no session_id) ─────────────────────────────────────────────

@patch("backend.src.nodes.load_session_node.create_session", new_callable=AsyncMock)
def test_new_session_creates_session(mock_create):
    """When session_id is blank, a new session is created in MongoDB."""
    mock_create.return_value = "new-session-abc"
    state = make_state(session_id="")

    from backend.src.nodes.load_session_node import load_session_node
    result = run(load_session_node(state))

    mock_create.assert_awaited_once()
    assert result["session_id"] == "new-session-abc"


@patch("backend.src.nodes.load_session_node.create_session", new_callable=AsyncMock)
def test_new_session_fallback_on_db_error(mock_create):
    """If MongoDB fails for new session, session_id defaults to 'local'."""
    mock_create.side_effect = Exception("DB unavailable")
    state = make_state(session_id="")

    from backend.src.nodes.load_session_node import load_session_node
    result = run(load_session_node(state))

    assert result["session_id"] == "local"


# ── Mid-session pass-through ─────────────────────────────────────────────────

def test_mid_session_passthrough():
    """When _mid_session=True, node returns state unchanged without DB call."""
    state = make_state(session_id="existing-session", _mid_session=True)

    with patch("backend.src.nodes.load_session_node.load_session") as mock_load:
        from backend.src.nodes.load_session_node import load_session_node
        result = run(load_session_node(state))
        mock_load.assert_not_called()

    assert result["session_id"] == "existing-session"


# ── Existing session (load from MongoDB) ─────────────────────────────────────

@patch("backend.src.nodes.load_session_node.load_session", new_callable=AsyncMock)
def test_existing_session_merges_state(mock_load):
    """When session_id exists, saved state is merged into current state."""
    mock_load.return_value = {
        "state": {
            "symptoms": ["fever", "cough"],
            "followup_count": 1,
            "risk_score": 3.5,
            "risk_level": "moderate",
            "risk_confidence": 0.7,
            "language": "en",
            "retrieved_info": ["Some info"],
        }
    }
    state = make_state(session_id="existing-session-xyz")

    from backend.src.nodes.load_session_node import load_session_node
    result = run(load_session_node(state))

    assert result["symptoms"] == ["fever", "cough"]
    assert result["followup_count"] == 1
    assert result["risk_score"] == 3.5
    assert result["risk_level"] == "moderate"


@patch("backend.src.nodes.load_session_node.load_session", new_callable=AsyncMock)
def test_existing_session_not_found(mock_load):
    """When session not found in DB, state is unchanged."""
    mock_load.return_value = None
    state = make_state(session_id="ghost-session")

    from backend.src.nodes.load_session_node import load_session_node
    result = run(load_session_node(state))

    # State unchanged — no crash
    assert result["session_id"] == "ghost-session"


@patch("backend.src.nodes.load_session_node.load_session", new_callable=AsyncMock)
def test_existing_session_db_error_is_safe(mock_load):
    """If MongoDB throws on load, node doesn't crash."""
    mock_load.side_effect = Exception("Timeout")
    state = make_state(session_id="existing-session")

    from backend.src.nodes.load_session_node import load_session_node
    result = run(load_session_node(state))  # Should not raise

    assert result is not None
