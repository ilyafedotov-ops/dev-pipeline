"""
Tests for JWT authentication backend.

Covers:
- Login with correct credentials → 200 + tokens
- Login with wrong password → 401
- /auth/me with valid token → user info
- /auth/me without token → 401
- /auth/me with expired token → 401
- /auth/refresh → new access token
- /auth/logout → token invalidated
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ADMIN_USER = "testadmin"
ADMIN_PASS = "test-secret-password-123"
JWT_SECRET = "test-jwt-secret-key-for-testing"


@pytest.fixture(autouse=True)
def _setup_auth_env(monkeypatch):
    """Configure JWT auth env vars for every test in this module."""
    monkeypatch.setenv("DEVGODZILLA_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("DEVGODZILLA_ADMIN_USERNAME", ADMIN_USER)
    monkeypatch.setenv("DEVGODZILLA_ADMIN_PASSWORD", ADMIN_PASS)
    # Reset config cache so the new env vars are picked up
    from devgodzilla.config import _reset_config_for_tests
    _reset_config_for_tests()
    yield
    _reset_config_for_tests()


@pytest.fixture()
def auth_client(test_client):
    """Return the standard test_client (already configured with temp DB,
    no API token requirement)."""
    return test_client


def _login(client, username: str = ADMIN_USER, password: str = ADMIN_PASS):
    """Helper to perform login and return the JSON response."""
    resp = client.post("/auth/login", json={"username": username, "password": password})
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_correct_credentials(self, auth_client):
        resp = _login(auth_client)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify the access token is a valid JWT
        payload = jwt.decode(data["access_token"], JWT_SECRET, algorithms=["HS256"])
        assert payload["sub"] == f"user:{ADMIN_USER}"
        assert payload["type"] == "access"
        assert payload["username"] == ADMIN_USER

    def test_login_wrong_password(self, auth_client):
        resp = _login(auth_client, password="wrong-password")
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    def test_login_wrong_username(self, auth_client):
        resp = _login(auth_client, username="nonexistent")
        assert resp.status_code == 401

    def test_login_not_configured(self, auth_client, monkeypatch):
        monkeypatch.delenv("DEVGODZILLA_ADMIN_USERNAME", raising=False)
        monkeypatch.delenv("DEVGODZILLA_ADMIN_PASSWORD", raising=False)
        from devgodzilla.config import _reset_config_for_tests
        _reset_config_for_tests()
        resp = _login(auth_client)
        assert resp.status_code == 401


class TestAuthMe:
    def test_me_with_valid_token(self, auth_client):
        login_resp = _login(auth_client)
        token = login_resp.json()["access_token"]
        resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == ADMIN_USER
        assert data["sub"] == f"user:{ADMIN_USER}"
        assert data["role"] == "admin"

    def test_me_without_token(self, auth_client):
        resp = auth_client.get("/auth/me")
        assert resp.status_code == 401
        assert "Not authenticated" in resp.json()["detail"]

    def test_me_with_expired_token(self, auth_client):
        config = auth_client.app  # not needed, just build token manually
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "devgodzilla",
            "sub": f"user:{ADMIN_USER}",
            "username": ADMIN_USER,
            "role": "admin",
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),  # expired 1 hour ago
        }
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        resp = auth_client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert resp.status_code == 401
        assert "expired" in resp.json()["detail"].lower()

    def test_me_with_invalid_token(self, auth_client):
        resp = auth_client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
        assert resp.status_code == 401


class TestRefresh:
    def test_refresh_returns_new_access_token(self, auth_client):
        login_resp = _login(auth_client)
        refresh_token = login_resp.json()["refresh_token"]

        resp = auth_client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify the new access token is valid
        payload = jwt.decode(data["access_token"], JWT_SECRET, algorithms=["HS256"])
        assert payload["type"] == "access"
        assert payload["sub"] == f"user:{ADMIN_USER}"

    def test_refresh_with_access_token_fails(self, auth_client):
        """Using an access token as a refresh token should fail."""
        login_resp = _login(auth_client)
        access_token = login_resp.json()["access_token"]

        resp = auth_client.post("/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401

    def test_refresh_with_expired_token_fails(self, auth_client):
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "devgodzilla",
            "sub": f"user:{ADMIN_USER}",
            "username": ADMIN_USER,
            "role": "admin",
            "type": "refresh",
            "jti": "fake-jti",
            "iat": now - timedelta(days=30),
            "exp": now - timedelta(days=15),
        }
        expired_refresh = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        resp = auth_client.post("/auth/refresh", json={"refresh_token": expired_refresh})
        assert resp.status_code == 401


class TestLogout:
    def test_logout_revokes_refresh_token(self, auth_client):
        login_resp = _login(auth_client)
        tokens = login_resp.json()
        refresh_token = tokens["refresh_token"]

        # Logout
        logout_resp = auth_client.post("/auth/logout", json={"refresh_token": refresh_token})
        assert logout_resp.status_code == 200

        # Refresh should now fail
        refresh_resp = auth_client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_resp.status_code == 401
        assert "revoked" in refresh_resp.json()["detail"].lower()

    def test_logout_then_login_still_works(self, auth_client):
        """After logout, a new login should still produce valid tokens."""
        login_resp = _login(auth_client)
        refresh_token = login_resp.json()["refresh_token"]
        auth_client.post("/auth/logout", json={"refresh_token": refresh_token})

        # Login again
        login_resp2 = _login(auth_client)
        assert login_resp2.status_code == 200
        new_tokens = login_resp2.json()
        # New refresh token should work
        refresh_resp = auth_client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
        assert refresh_resp.status_code == 200
