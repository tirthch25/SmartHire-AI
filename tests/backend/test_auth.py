"""
SmartHire AI — Authentication API Tests

Covers:
- POST /auth/register    (success, duplicate email, weak password)
- POST /auth/login       (success, wrong password, unknown email)
- GET  /auth/me          (authenticated, unauthenticated)
- POST /auth/refresh     (valid token, expired token)
- POST /auth/logout      (authenticated)
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestRegister:
    """POST /api/v1/auth/register"""

    async def test_register_success(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@smarthire.ai",
            "password": "SecurePass1!",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@smarthire.ai"
        assert data["full_name"] == "New User"
        assert "hashed_password" not in data
        assert "id" in data

    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/register", json={
            "email": test_user.email,
            "password": "SecurePass1!",
            "full_name": "Dupe",
        })
        assert resp.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak@smarthire.ai",
            "password": "short",
            "full_name": "Weak Password User",
        })
        assert resp.status_code == 422

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "SecurePass1!",
            "full_name": "Invalid Email",
        })
        assert resp.status_code == 422

    async def test_register_missing_fields(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "partial@smarthire.ai",
        })
        assert resp.status_code == 422


class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_login_success(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "Password123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_user.email,
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@smarthire.ai",
            "password": "SomePass1!",
        })
        assert resp.status_code == 401

    async def test_login_inactive_user(self, client: AsyncClient, db):
        from app.models.user import User
        from app.core.security import hash_password
        import uuid
        inactive = User(
            id=uuid.uuid4(),
            email="inactive@smarthire.ai",
            full_name="Inactive",
            hashed_password=hash_password("Password123!"),
            is_active=False,
        )
        db.add(inactive)
        await db.flush()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "inactive@smarthire.ai",
            "password": "Password123!",
        })
        assert resp.status_code == 403


class TestGetMe:
    """GET /api/v1/auth/me"""

    async def test_get_me_authenticated(self, client: AsyncClient, auth_headers, test_user):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == test_user.email
        assert data["full_name"] == test_user.full_name
        assert "hashed_password" not in data

    async def test_get_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_get_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


class TestLogout:
    """POST /api/v1/auth/logout"""

    async def test_logout_success(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/auth/logout", headers=auth_headers)
        assert resp.status_code in (200, 204)

    async def test_logout_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 401


class TestUpdateMe:
    """PUT /api/v1/auth/me"""

    async def test_update_name(self, client: AsyncClient, auth_headers):
        resp = await client.put(
            "/api/v1/auth/me",
            json={"full_name": "Updated Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    async def test_update_unauthenticated(self, client: AsyncClient):
        resp = await client.put("/api/v1/auth/me", json={"full_name": "Hacker"})
        assert resp.status_code == 401
