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


def test_image_endpoint_returns_graph_final_response(client, mock_graph):
    """Image route should return final_response/structured text when graph provides it."""
    mock_graph.ainvoke = AsyncMock(return_value={
        "messages": [
            {"role": "user", "content": "Analyze this medical image"},
            {"role": "assistant", "content": "Short summary"},
        ],
        "final_response": "### 🧾 Symptoms Identified\n\n• rash\n\n---\n\n### 🩺 Possible Conditions\n\nPossible causes include eczema.",
        "risk_level": "low",
        "vision_findings": {"image_type": "skin"},
    })

    small_image = b"\xff\xd8\xff\xe0" + b"\x00" * 50
    resp = client.post(
        "/api/v3/image",
        files={"image": ("test.jpg", small_image, "image/jpeg")},
        data={"user_id": "test-user", "image_type_hint": "body"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"].startswith("### 🧾 Symptoms Identified")
    assert body["response"].startswith("### 🧾 Symptoms Identified")


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


@patch("backend.src.api.routes.text_to_speech", return_value="")
@patch("backend.src.api.routes.transcribe_audio")
def test_voice_endpoint_uses_graph_audio_and_normalized_language(mock_transcribe, mock_tts, client, mock_graph):
    """Voice route should normalize detected language and reuse graph-generated audio output."""
    mock_transcribe.return_value = {
        "text": "I think I am having a heart attack",
        "language": "English",
    }
    mock_graph.ainvoke = AsyncMock(return_value={
        "messages": [
            {"role": "user", "content": "I think I am having a heart attack"},
            {"role": "assistant", "content": "Call emergency services now."},
        ],
        "session_id": "voice-session",
        "risk_level": "critical",
        "final_response": "Call emergency services now.",
        "audio_url": "graph-generated.mp3",
    })

    audio_bytes = b"RIFF" + b"\x00" * 64
    resp = client.post(
        "/api/v3/voice",
        files={"audio": ("sample.wav", audio_bytes, "audio/wav")},
        data={"user_id": "voice-user", "language": "English"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "critical"
    assert body["audio_path"] == "graph-generated.mp3"
    assert body["audio_url"].endswith("/static/audio/graph-generated.mp3")
    mock_tts.assert_not_called()

    graph_state = mock_graph.ainvoke.await_args.args[0]
    assert graph_state["language"] == "en"
    assert graph_state["user_consent_for_call"] is False


@patch("backend.src.api.routes.text_to_speech", return_value="fallback.mp3")
@patch("backend.src.api.routes.transcribe_audio")
def test_voice_endpoint_falls_back_to_route_tts_with_normalized_language(mock_transcribe, mock_tts, client, mock_graph):
    """If graph TTS output is missing, the route fallback should still use normalized language."""
    mock_transcribe.return_value = {
        "text": "I have chest pain",
        "language": "English",
    }
    mock_graph.ainvoke = AsyncMock(return_value={
        "messages": [
            {"role": "user", "content": "I have chest pain"},
            {"role": "assistant", "content": "Please seek urgent care now."},
        ],
        "session_id": "voice-session",
        "risk_level": "high",
        "final_response": "Please seek urgent care now.",
        "audio_url": "",
    })

    audio_bytes = b"RIFF" + b"\x00" * 64
    resp = client.post(
        "/api/v3/voice",
        files={"audio": ("sample.wav", audio_bytes, "audio/wav")},
        data={"user_id": "voice-user", "language": "English"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["audio_path"] == "fallback.mp3"
    assert body["audio_url"].endswith("/static/audio/fallback.mp3")
    mock_tts.assert_called_once_with("Please seek urgent care now.", "en")


@patch("backend.src.api.routes.text_to_speech", return_value="")
@patch("backend.src.api.routes.transcribe_audio")
def test_voice_endpoint_respects_explicit_call_consent(mock_transcribe, mock_tts, client, mock_graph):
    """Voice route must forward explicit user_consent_for_call=True when provided."""
    mock_transcribe.return_value = {
        "text": "I have severe chest pain",
        "language": "English",
    }
    mock_graph.ainvoke = AsyncMock(return_value={
        "messages": [
            {"role": "user", "content": "I have severe chest pain"},
            {"role": "assistant", "content": "Please seek urgent care now."},
        ],
        "session_id": "voice-session",
        "risk_level": "high",
        "final_response": "Please seek urgent care now.",
        "audio_url": "graph-generated.mp3",
    })

    audio_bytes = b"RIFF" + b"\x00" * 64
    resp = client.post(
        "/api/v3/voice",
        files={"audio": ("sample.wav", audio_bytes, "audio/wav")},
        data={"user_id": "voice-user", "language": "English", "user_consent_for_call": "true"},
    )

    assert resp.status_code == 200
    graph_state = mock_graph.ainvoke.await_args.args[0]
    assert graph_state["user_consent_for_call"] is True
    mock_tts.assert_not_called()

