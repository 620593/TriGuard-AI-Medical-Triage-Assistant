import os
import pytest
from datetime import timedelta, datetime, timezone
import jwt
import bcrypt

# Set JWT_SECRET_KEY before importing security to avoid RuntimeError
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")

from backend.src.tools.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

def test_get_password_hash_returns_valid_hash():
    password = "supersecretpassword123"
    hashed = get_password_hash(password)

    assert hashed != password
    assert isinstance(hashed, str)
    # A bcrypt hash starts with $2b$, $2a$, etc.
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    # We should be able to verify it with bcrypt directly
    assert bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def test_verify_password_matching_passwords():
    password = "supersecretpassword123"
    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True

def test_verify_password_non_matching_passwords():
    password = "supersecretpassword123"
    wrong_password = "wrongpassword"
    hashed = get_password_hash(password)

    assert verify_password(wrong_password, hashed) is False

def test_password_truncation():
    # bcrypt limits passwords to 72 bytes.
    # The security tool truncates it manually to 72 bytes.
    long_password = "a" * 100

    hashed = get_password_hash(long_password)

    # Since it's truncated, matching the first 72 bytes should work
    assert verify_password(long_password, hashed) is True
    # And specifically, a password that's the same up to 72 bytes should match.
    # Wait, the tool itself truncates during verification.
    assert verify_password(long_password[:72], hashed) is True

    # But if we change something before 72 bytes, it should fail
    modified_long_password = "b" + "a" * 99
    assert verify_password(modified_long_password, hashed) is False

def test_verify_password_handles_exceptions():
    password = "supersecretpassword123"
    # An invalid hash format
    invalid_hash = "not-a-valid-bcrypt-hash"

    # checkpw will raise ValueError, verify_password should catch it and return False
    assert verify_password(password, invalid_hash) is False

    # None inputs (should raise TypeError inside, caught and returns False)
    assert verify_password(password, None) is False # type: ignore
    assert verify_password(None, invalid_hash) is False # type: ignore

def test_create_access_token_standard_expiration():
    data = {"sub": "testuser"}
    token = create_access_token(data)

    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "testuser"
    assert "exp" in decoded

    # Token should expire in roughly ACCESS_TOKEN_EXPIRE_MINUTES
    exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    expected_exp = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Allow some tolerance for execution time
    assert abs((exp_time - expected_exp).total_seconds()) < 10

def test_create_access_token_custom_expiration():
    data = {"sub": "testuser"}
    expires_delta = timedelta(minutes=15)
    token = create_access_token(data, expires_delta=expires_delta)

    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "testuser"
    assert "exp" in decoded

    exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
    expected_exp = datetime.now(timezone.utc) + expires_delta

    assert abs((exp_time - expected_exp).total_seconds()) < 10

def test_decode_access_token_valid():
    data = {"sub": "testuser"}
    token = create_access_token(data)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "testuser"
    assert "exp" in decoded

def test_decode_access_token_expired():
    data = {"sub": "testuser"}
    # Create token that expired 1 minute ago
    expires_delta = timedelta(minutes=-1)
    token = create_access_token(data, expires_delta=expires_delta)

    decoded = decode_access_token(token)
    assert decoded is None

def test_decode_access_token_invalid_token():
    invalid_token = "this.is.not.a.valid.jwt.token"
    decoded = decode_access_token(invalid_token)
    assert decoded is None
