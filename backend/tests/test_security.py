import pytest
from datetime import timedelta
import jwt
from backend.src.tools.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    SECRET_KEY,
    ALGORITHM,
)

def test_verify_password_correct():
    password = "supersecretpassword123"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed) is True

def test_verify_password_incorrect():
    password = "supersecretpassword123"
    wrong_password = "wrongpassword"
    hashed = get_password_hash(password)
    assert verify_password(wrong_password, hashed) is False

def test_verify_password_invalid_hash():
    password = "supersecretpassword123"
    assert verify_password(password, "invalid_hash_string") is False

def test_verify_password_truncate_long_password():
    # Passwords over 72 bytes should be truncated
    long_password = "a" * 100
    hashed = get_password_hash(long_password)
    assert verify_password(long_password, hashed) is True

    # Truncated versions should also verify as True since the hash was generated on the truncated part
    truncated_password = ("a" * 100).encode('utf-8')[:72].decode('utf-8')
    assert verify_password(truncated_password, hashed) is True

def test_get_password_hash_generates_valid_bcrypt():
    password = "mypassword"
    hashed = get_password_hash(password)
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$") or hashed.startswith("$2y$")

def test_create_access_token_default_expiration():
    data = {"sub": "user123"}
    token = create_access_token(data)

    # Verify we can decode it with jwt directly
    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "user123"
    assert "exp" in decoded

def test_create_access_token_custom_expiration():
    data = {"sub": "user123"}
    expires_delta = timedelta(minutes=15)
    token = create_access_token(data, expires_delta=expires_delta)

    decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded["sub"] == "user123"
    assert "exp" in decoded

def test_decode_access_token_valid():
    data = {"sub": "user123"}
    token = create_access_token(data)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user123"

def test_decode_access_token_invalid():
    invalid_token = "this.is.not.a.valid.token"
    decoded = decode_access_token(invalid_token)
    assert decoded is None

def test_decode_access_token_expired():
    data = {"sub": "user123"}
    # Create an expired token by passing negative timedelta
    expires_delta = timedelta(minutes=-15)
    token = create_access_token(data, expires_delta=expires_delta)

    decoded = decode_access_token(token)
    assert decoded is None
