"""
test_routes.py
--------------
Tests for all FastAPI routes using TestClient (no real server needed).
Uses `app` directly with mocked app.state.graph — bypasses lifespan entirely.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set env vars before any app import
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")


def _make_mock_result(risk="low", response="🩺 Test response.", session="test-session"):
    return {
        "messages": [
            {"role": "user", "content": "test"},
            {"role": "assistant", "content": response},
        ],
        "session_id": session,
        "risk_level": risk,
        "vision_findings": {},
        "audio_url": "",
    }


@pytest.fixture(scope="module")
def app_with_mock_graph():
    """
    Returns the FastAPI app with a mocked graph injected into app.state.
    Uses lifespan=False so no DB/graph startup code runs.
    """
    from fastapi.testclient import TestClient
    from backend.src.main import app

    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(return_value=_make_mock_result())
    app.state.graph = mock_graph

    # TestClient with lifespan disabled to skip startup hooks
    client = TestClient(app, raise_server_exceptions=False)
    return client, mock_graph


@pytest.fixture()
def client(app_with_mock_graph):
    c, _ = app_with_mock_graph
    return c


@pytest.fixture()
def mock_graph(app_with_mock_graph):
    _, g = app_with_mock_graph
    return g


# ── /health ────────────────────────────────────────────────────────────────

def test_health_endpoint(client):
    """Health endpoint always returns 200 with status:healthy."""
    resp = client.get("/api/v3/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


# ── /triage ───────────────────────────────────────────────────────────────

def test_triage_returns_session_response_risk(client, mock_graph):
    """Text triage returns session_id, response, and risk_level."""
    mock_graph.ainvoke = AsyncMock(return_value=_make_mock_result(session="abc-123"))
    resp = client.post("/api/v3/triage", json={
        "message": "I have fever and cough",
        "user_id": "test-user",
        "language": "en",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "session_id" in body
    assert "response" in body
    assert "risk_level" in body


def test_triage_invalid_user_id_rejected(client):
    """Pydantic rejects user_ids containing invalid characters."""
    resp = client.post("/api/v3/triage", json={
        "message": "I have fever",
        "user_id": "bad id!@#",
    })
    # Pydantic V2 raises 422 for field_validator failures
    assert resp.status_code == 422


def test_triage_anonymous_user_allowed(client, mock_graph):
    """Requests without user_id default to 'anonymous'."""
    mock_graph.ainvoke = AsyncMock(return_value=_make_mock_result())
    resp = client.post("/api/v3/triage", json={"message": "I feel unwell"})
    assert resp.status_code == 200


def test_triage_missing_message_rejected(client):
    """Missing required field 'message' returns 422."""
    resp = client.post("/api/v3/triage", json={"user_id": "test-user"})
    assert resp.status_code == 422


# ── /image ────────────────────────────────────────────────────────────────

def test_image_endpoint_rejects_oversized_file(client):
    """Image endpoint rejects files >10MB with 413 Request Entity Too Large."""
    big_file = b"\xff\xd8\xff" + b"\x00" * (10 * 1024 * 1024 + 10)
    resp = client.post(
        "/api/v3/image",
        files={"image": ("big.jpg", big_file, "image/jpeg")},
        data={"user_id": "test-user"},
    )
    assert resp.status_code == 413


def test_image_endpoint_rejects_invalid_user_id(client):
    """Image endpoint rejects user_ids with spaces/special chars."""
    small_image = b"\xff\xd8\xff\xe0" + b"\x00" * 50
    resp = client.post(
        "/api/v3/image",
        files={"image": ("test.jpg", small_image, "image/jpeg")},
        data={"user_id": "bad id!@#"},
    )
    assert resp.status_code == 400


# ── /sessions ─────────────────────────────────────────────────────────────

@patch("backend.src.api.routes.list_user_sessions", new_callable=AsyncMock,
       return_value=[{"session_id": "abc", "created_at": "2026-01-01"}])
def test_sessions_valid_user(mock_sessions, client):
    """Sessions endpoint returns list for a valid user header."""
    resp = client.get("/api/v3/sessions", headers={"x-user-id": "test-user"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@patch("backend.src.api.routes.list_user_sessions", new_callable=AsyncMock, return_value=[])
def test_sessions_invalid_user_id_rejected(mock_sessions, client):
    """Sessions endpoint rejects user IDs that fail regex validation."""
    resp = client.get("/api/v3/sessions", headers={"x-user-id": "bad id!@#"})
    assert resp.status_code == 400


@patch("backend.src.api.routes.list_user_sessions", new_callable=AsyncMock, return_value=[])
def test_sessions_no_header_returns_anonymous(mock_sessions, client):
    """Sessions endpoint with no user header defaults to 'anonymous'."""
    resp = client.get("/api/v3/sessions")
    assert resp.status_code == 200


# ── /reports ─────────────────────────────────────────────────────────────

@patch("backend.src.api.routes.list_user_reports", new_callable=AsyncMock,
       return_value=[{"risk_level": "low", "session_id": "abc"}])
def test_reports_valid_user(mock_reports, client):
    """Reports endpoint returns a list for a valid user."""
    resp = client.get("/api/v3/reports", headers={"x-user-id": "test-user"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@patch("backend.src.api.routes.list_user_reports", new_callable=AsyncMock, return_value=[])
def test_reports_invalid_user_rejected(mock_reports, client):
    """Reports endpoint rejects invalid user IDs."""
    resp = client.get("/api/v3/reports", headers={"x-user-id": "@@invalid"})
    assert resp.status_code == 400
