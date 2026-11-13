"""
Unit tests for core configuration and utilities.
These tests do NOT require a running database or Redis.
"""
import os
import pytest


def test_settings_load():
    """Settings should load with environment variables set."""
    from app.core.config import settings
    assert settings.APP_ENV == "testing"
    assert settings.SECRET_KEY != ""
    assert len(settings.SECRET_KEY) >= 32


def test_settings_database_url():
    """DATABASE_URL should be configured."""
    from app.core.config import settings
    assert settings.DATABASE_URL != ""
    assert "postgresql" in settings.DATABASE_URL


def test_settings_redis_url():
    """REDIS_URL should be configured."""
    from app.core.config import settings
    assert settings.REDIS_URL != ""


def test_settings_allowed_origins_default():
    """ALLOWED_ORIGINS should default sensibly."""
    from app.core.config import settings
    # In testing mode, may be empty or localhost — just ensure it's a list or string
    assert settings.ALLOWED_ORIGINS is not None


def test_jwt_token_encode_decode():
    """JWT tokens should round-trip correctly."""
    from app.core.security import create_access_token, decode_token
    user_id = "test-user-123"
    token = create_access_token(user_id)
    assert token is not None
    payload = decode_token(token, expected_type="access")
    assert payload is not None
    assert payload.get("sub") == user_id


def test_password_hash_verify():
    """Password hash/verify should work correctly."""
    from app.core.security import hash_password, verify_password
    plain = "MySecurePassword123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("WrongPassword", hashed)
