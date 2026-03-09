import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
import os
import urllib.parse

from backend.src.main import app

# Create a test client
client = TestClient(app, raise_server_exceptions=False)

def test_google_login_sets_state():
    """Verify that google_login sets the oauth_state cookie and appends state to the URL."""
    # We should prevent redirect from happening so we can inspect the response headers
    response = client.get("/api/v3/auth/google", follow_redirects=False)

    assert response.status_code == 307  # Temporary Redirect

    # Check that oauth_state cookie is set
    assert "oauth_state" in response.cookies
    cookie_state = response.cookies["oauth_state"]
    assert len(cookie_state) > 10

    # Check that state parameter is in the redirect URL
    location = response.headers.get("location")
    assert location is not None

    parsed_url = urllib.parse.urlparse(location)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    assert "state" in query_params
    assert query_params["state"][0] == cookie_state

def test_google_callback_missing_state():
    """Verify that google_callback raises 400 when state is missing."""
    response = client.get("/api/v3/auth/google/callback?code=testcode", follow_redirects=False)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid state parameter. CSRF attempt suspected."

def test_google_callback_invalid_state():
    """Verify that google_callback raises 400 when state doesn't match the cookie."""
    client.cookies.set("oauth_state", "real-state-123")
    response = client.get("/api/v3/auth/google/callback?code=testcode&state=fake-state-456", follow_redirects=False)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid state parameter. CSRF attempt suspected."

@patch("backend.src.api.auth.httpx.AsyncClient.post", new_callable=AsyncMock)
@patch("backend.src.api.auth.httpx.AsyncClient.get", new_callable=AsyncMock)
@patch("backend.src.api.auth.get_user_by_email", new_callable=AsyncMock)
@patch("backend.src.api.auth.create_user", new_callable=AsyncMock)
@patch("backend.src.api.auth.create_access_token")
def test_google_callback_valid_state(mock_create_access_token, mock_create_user, mock_get_user, mock_get, mock_post):
    """Verify that google_callback works when state matches and deletes the cookie."""
    # Mock token response
    class MockPostResp:
        status_code = 200
        def json(self): return {"access_token": "fake-google-token"}
    mock_post.return_value = MockPostResp()

    # Mock user info response
    class MockGetResp:
        status_code = 200
        def json(self): return {"email": "test@example.com", "name": "Test User"}
    mock_get.return_value = MockGetResp()

    # Mock database interactions
    mock_get_user.return_value = {"user_id": "test-id", "email": "test@example.com", "_id": "test-id"}

    # Mock access token creation
    mock_create_access_token.return_value = "fake-jwt-token"

    client.cookies.set("oauth_state", "valid-state-123")
    response = client.get("/api/v3/auth/google/callback?code=testcode&state=valid-state-123", follow_redirects=False)

    assert response.status_code == 307

    # Check that oauth_state cookie is deleted (Max-Age=0 or empty value)
    cookie_header = response.headers.get("set-cookie")
    assert cookie_header is not None
    assert "oauth_state=" in cookie_header
    assert "Max-Age=0" in cookie_header or 'oauth_state="";' in cookie_header or 'oauth_state=""' in cookie_header
