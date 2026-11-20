"""
Integration tests for the SmartHire AI FastAPI application.
Requires running PostgreSQL + Redis (provided by CI services).
"""
import pytest
from httpx import AsyncClient, ASGITransport


async def test_health_check():
    """The /health endpoint should return 200 with status healthy or degraded."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert body["status"] in ("healthy", "degraded")


async def test_api_health_check():
    """The /api/health endpoint should also return 200."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
    assert response.status_code == 200


async def test_openapi_schema():
    """The OpenAPI schema should be accessible."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/openapi.json")
    assert response.status_code == 200
    body = response.json()
    assert "openapi" in body
    assert "paths" in body


async def test_auth_required_on_protected_route():
    """Protected routes should return 401/403 without a token."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/resume/list")
    assert response.status_code in (401, 403)
