import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Set env vars before any app import
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-12345678901234567890")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://test-redirect-uri")
os.environ.setdefault("FRONTEND_URL", "http://test-frontend-url")

# Create a small FastAPI app just for testing the auth router
from backend.src.api.auth import router as auth_router

app = FastAPI()
app.include_router(auth_router, prefix="/api/v3/auth")

client = TestClient(app)

@patch("backend.src.api.auth.get_user_by_email", new_callable=AsyncMock)
@patch("backend.src.api.auth.create_user", new_callable=AsyncMock)
def test_register_success(mock_create_user, mock_get_user_by_email):
    """Test successful user registration."""
    # Setup mock to return None, meaning email is not registered
    mock_get_user_by_email.return_value = None

    response = client.post("/api/v3/auth/register", json={
        "name": "Test User",
        "email": "test@example.com",
        "password": "strongpassword123"
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["name"] == "Test User"
    assert "user_id" in data

    # Verify the mocks were called
    mock_get_user_by_email.assert_called_once_with("test@example.com")
    mock_create_user.assert_called_once()

    # Verify create_user arguments
    user_data_arg = mock_create_user.call_args[0][0]
    assert user_data_arg["name"] == "Test User"
    assert user_data_arg["email"] == "test@example.com"
    assert "hashed_password" in user_data_arg
    assert user_data_arg["user_id"] == data["user_id"]

@patch("backend.src.api.auth.get_user_by_email", new_callable=AsyncMock)
@patch("backend.src.api.auth.create_user", new_callable=AsyncMock)
def test_register_conflict(mock_create_user, mock_get_user_by_email):
    """Test user registration with existing email."""
    # Setup mock to return a user dictionary, meaning email is already registered
    mock_get_user_by_email.return_value = {"user_id": "existing-123"}

    response = client.post("/api/v3/auth/register", json={
        "name": "Test User",
        "email": "test@example.com",
        "password": "strongpassword123"
    })

    assert response.status_code == 409
    data = response.json()
    assert data["detail"] == "Email already registered"

    # Verify get_user_by_email was called, but create_user was NOT called
    mock_get_user_by_email.assert_called_once_with("test@example.com")
    mock_create_user.assert_not_called()

@patch("backend.src.api.auth.get_user_by_email", new_callable=AsyncMock)
@patch("backend.src.api.auth.verify_password")
def test_login_success(mock_verify_password, mock_get_user_by_email):
    """Test successful login."""
    # Mock user data and password verification
    mock_get_user_by_email.return_value = {
        "user_id": "existing-123",
        "name": "Existing User",
        "hashed_password": "hashed_password_string"
    }
    mock_verify_password.return_value = True

    response = client.post("/api/v3/auth/login", json={
        "email": "test@example.com",
        "password": "correctpassword"
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user_id"] == "existing-123"
    assert data["name"] == "Existing User"

    mock_get_user_by_email.assert_called_once_with("test@example.com")
    mock_verify_password.assert_called_once_with("correctpassword", "hashed_password_string")


@patch("backend.src.api.auth.get_user_by_email", new_callable=AsyncMock)
def test_login_unauthorized_user(mock_get_user_by_email):
    """Test login with an unregistered email."""
    # Return None for unregistered email
    mock_get_user_by_email.return_value = None

    response = client.post("/api/v3/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "somepassword"
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"
    mock_get_user_by_email.assert_called_once_with("nonexistent@example.com")


@patch("backend.src.api.auth.get_user_by_email", new_callable=AsyncMock)
@patch("backend.src.api.auth.verify_password")
def test_login_unauthorized_password(mock_verify_password, mock_get_user_by_email):
    """Test login with an incorrect password."""
    # Return valid user
    mock_get_user_by_email.return_value = {
        "user_id": "existing-123",
        "name": "Existing User",
        "hashed_password": "hashed_password_string"
    }
    # Return false for password verification
    mock_verify_password.return_value = False

    response = client.post("/api/v3/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"

    mock_get_user_by_email.assert_called_once_with("test@example.com")
    mock_verify_password.assert_called_once_with("wrongpassword", "hashed_password_string")


def test_google_login():
    """Test the Google OAuth redirect endpoint."""
    # We use follow_redirects=False to catch the redirect response
    response = client.get("/api/v3/auth/google", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=test-client-id" in location
    assert "redirect_uri=http://test-redirect-uri" in location


@patch("backend.src.api.auth.httpx.AsyncClient")
@patch("backend.src.api.auth.get_user_by_email", new_callable=AsyncMock)
@patch("backend.src.api.auth.create_user", new_callable=AsyncMock)
def test_google_callback_new_user(mock_create_user, mock_get_user_by_email, mock_async_client_class):
    """Test Google OAuth callback for a new user."""
    # Setup mock for httpx.AsyncClient
    mock_client_instance = AsyncMock()
    # The context manager (`async with httpx.AsyncClient() as client:`) returns the instance
    mock_async_client_class.return_value.__aenter__.return_value = mock_client_instance

    # Mock the response for the token request
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {"access_token": "mock_google_token"}
    mock_client_instance.post.return_value = mock_token_response

    # Mock the response for the user info request
    mock_user_info_response = MagicMock()
    mock_user_info_response.status_code = 200
    mock_user_info_response.json.return_value = {
        "email": "newgoogleuser@example.com",
        "name": "Google User"
    }
    mock_client_instance.get.return_value = mock_user_info_response

    # Setup database mocks
    mock_get_user_by_email.return_value = None  # User doesn't exist

    response = client.get("/api/v3/auth/google/callback?code=mock_code", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert location.startswith("http://test-frontend-url/dashboard?token=")
    assert "name=Google%20User" in location
    assert "uid=" in location

    # Verify db calls
    mock_get_user_by_email.assert_called_once_with("newgoogleuser@example.com")
    mock_create_user.assert_called_once()

    user_data_arg = mock_create_user.call_args[0][0]
    assert user_data_arg["email"] == "newgoogleuser@example.com"
    assert user_data_arg["name"] == "Google User"
    assert user_data_arg["google_oauth"] is True


@patch("backend.src.api.auth.httpx.AsyncClient")
@patch("backend.src.api.auth.get_user_by_email", new_callable=AsyncMock)
@patch("backend.src.api.auth.create_user", new_callable=AsyncMock)
def test_google_callback_existing_user(mock_create_user, mock_get_user_by_email, mock_async_client_class):
    """Test Google OAuth callback for an existing user."""
    # Setup mock for httpx.AsyncClient
    mock_client_instance = AsyncMock()
    mock_async_client_class.return_value.__aenter__.return_value = mock_client_instance

    # Mock the response for the token request
    mock_token_response = MagicMock()
    mock_token_response.status_code = 200
    mock_token_response.json.return_value = {"access_token": "mock_google_token"}
    mock_client_instance.post.return_value = mock_token_response

    # Mock the response for the user info request
    mock_user_info_response = MagicMock()
    mock_user_info_response.status_code = 200
    mock_user_info_response.json.return_value = {
        "email": "existinggoogleuser@example.com",
        "name": "Existing Google User"
    }
    mock_client_instance.get.return_value = mock_user_info_response

    # Setup database mocks
    mock_get_user_by_email.return_value = {
        "_id": "existing-id-123",
        "user_id": "existing-uid-123",
        "email": "existinggoogleuser@example.com"
    }

    response = client.get("/api/v3/auth/google/callback?code=mock_code", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers.get("location", "")
    assert location.startswith("http://test-frontend-url/dashboard?token=")
    assert "name=Existing%20Google%20User" in location
    assert "uid=existing-uid-123" in location

    # Verify db calls
    mock_get_user_by_email.assert_called_once_with("existinggoogleuser@example.com")
    mock_create_user.assert_not_called()
