import os
import pytest
from datetime import timedelta

# Set up environment variable before importing the security module
# The key needs to be at least 32 bytes to avoid InsecureKeyLengthWarning from pyjwt
os.environ["JWT_SECRET_KEY"] = "this_is_a_very_secure_test_secret_key_that_is_long_enough"

from backend.src.tools.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)

def test_get_and_verify_password_success():
    password = "supersecretpassword123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True

def test_verify_password_incorrect():
    password = "supersecretpassword123!"
    hashed = get_password_hash(password)

    assert verify_password("wrongpassword", hashed) is False

def test_verify_password_long_string():
    # Passwords longer than 72 bytes are truncated internally
    password = "a" * 100
    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True
    # Verify that truncation works exactly as expected (72 bytes match)
    assert verify_password("a" * 72, hashed) is True
    # And that a shorter one does not match
    assert verify_password("a" * 71, hashed) is False

def test_verify_password_invalid_hash():
    password = "supersecretpassword123!"
    invalid_hash = "not-a-valid-bcrypt-hash"

    # verify_password catches all Exceptions and returns False
    assert verify_password(password, invalid_hash) is False

def test_create_and_decode_access_token():
    data = {"sub": "user_id_123"}
    token = create_access_token(data)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == data["sub"]
    assert "exp" in decoded

def test_create_access_token_with_expires_delta():
    data = {"sub": "user_id_456"}
    # Token expires in 1 minute
    delta = timedelta(minutes=1)
    token = create_access_token(data, expires_delta=delta)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == data["sub"]
    assert "exp" in decoded

def test_decode_invalid_access_token():
    invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature"
    decoded = decode_access_token(invalid_token)

    # decode_access_token catches PyJWTError and returns None
    assert decoded is None

def test_decode_expired_access_token():
    data = {"sub": "user_id_789"}
    # Token expired 1 minute ago
    delta = timedelta(minutes=-1)
    token = create_access_token(data, expires_delta=delta)

    decoded = decode_access_token(token)

    # decode_access_token catches ExpiredSignatureError (a subclass of PyJWTError) and returns None
    assert decoded is None
