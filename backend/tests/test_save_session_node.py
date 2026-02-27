"""
test_save_session_node.py
--------------------------
Tests for save_session_node: saves to MongoDB, skip on local session.
"""

import pytest
from unittest.mock import AsyncMock, patch
from backend.tests.helpers import make_state
import asyncio


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


MOCK_UPDATE = "backend.src.nodes.save_session_node.update_session"
MOCK_REPORT = "backend.src.nodes.save_session_node.save_report"
MOCK_LOG = "backend.src.nodes.save_session_node.insert_log"


@patch(MOCK_LOG, new_callable=AsyncMock)
@patch(MOCK_REPORT, new_callable=AsyncMock)
@patch(MOCK_UPDATE, new_callable=AsyncMock)
def test_session_saved_to_mongodb(mock_update, mock_report, mock_log):
    """When session_id is valid, update_session and save_report are called."""
    state = make_state(
        session_id="real-session-abc",
        messages=[{"role": "user", "content": "I have fever"}],
        symptoms=["fever"],
        risk_level="low",
        risk_score=2.5,
    )

    from backend.src.nodes.save_session_node import save_session_node
    result = run(save_session_node(state))

    mock_update.assert_awaited_once()
    mock_report.assert_awaited_once()


@patch(MOCK_LOG, new_callable=AsyncMock)
@patch(MOCK_REPORT, new_callable=AsyncMock)
@patch(MOCK_UPDATE, new_callable=AsyncMock)
def test_local_session_skips_db(mock_update, mock_report, mock_log):
    """When session_id == 'local', no DB calls are made."""
    state = make_state(session_id="local")

    from backend.src.nodes.save_session_node import save_session_node
    result = run(save_session_node(state))

    mock_update.assert_not_called()
    mock_report.assert_not_called()


@patch(MOCK_LOG, new_callable=AsyncMock)
@patch(MOCK_REPORT, new_callable=AsyncMock)
@patch(MOCK_UPDATE, new_callable=AsyncMock)
def test_empty_session_id_skips_db(mock_update, mock_report, mock_log):
    """When session_id is empty, no DB calls are made."""
    state = make_state(session_id="")

    from backend.src.nodes.save_session_node import save_session_node
    result = run(save_session_node(state))

    mock_update.assert_not_called()


@patch(MOCK_LOG, new_callable=AsyncMock)
@patch(MOCK_REPORT, new_callable=AsyncMock)
@patch(MOCK_UPDATE, new_callable=AsyncMock)
def test_save_handles_db_error_gracefully(mock_update, mock_report, mock_log):
    """If update_session throws, the node doesn't crash and returns state."""
    mock_update.side_effect = Exception("Mongo timeout")
    state = make_state(session_id="real-session")

    from backend.src.nodes.save_session_node import save_session_node
    result = run(save_session_node(state))  # Must not raise

    assert result is not None


@patch(MOCK_LOG, new_callable=AsyncMock)
@patch(MOCK_REPORT, new_callable=AsyncMock)
@patch(MOCK_UPDATE, new_callable=AsyncMock)
def test_report_not_saved_during_followup(mock_update, mock_report, mock_log):
    """Report is NOT saved when next_action == 'ask_followup' (session still active)."""
    state = make_state(session_id="real-session", next_action="ask_followup")

    from backend.src.nodes.save_session_node import save_session_node
    result = run(save_session_node(state))

    mock_update.assert_awaited_once()  # Session IS updated
    mock_report.assert_not_called()    # But report is NOT saved
