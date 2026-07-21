"""
SmartHire AI — Dashboard API Tests

Covers:
- GET /dashboard/stats      (returns correct counts and scores)
- GET /dashboard/analytics  (score trend + component averages + top jobs)
- GET /dashboard/activity   (recent activity feed)

All tests verify response structure and type correctness.
Redis caching is not tested here (unit-tested separately).
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.models.analysis import ATSAnalysis

pytestmark = pytest.mark.asyncio


class TestDashboardStats:
    """GET /api/v1/dashboard/stats"""

    @patch("app.api.v1.dashboard.analytics_service")
    async def test_stats_structure(self, mock_service, client: AsyncClient, auth_headers):
        mock_service.get_stats = AsyncMock(return_value={
            "total_resumes": 5,
            "total_analyses": 12,
            "total_jobs": 8,
            "total_cover_letters": 3,
            "average_ats_score": 71.4,
            "best_ats_score": 88.0,
            "last_upload": "2026-07-15T10:00:00Z",
        })
        resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_resumes"] == 5
        assert data["total_analyses"] == 12
        assert data["total_jobs"] == 8
        assert data["total_cover_letters"] == 3
        assert data["average_ats_score"] == pytest.approx(71.4, rel=0.01)
        assert data["best_ats_score"] == pytest.approx(88.0, rel=0.01)
        assert "last_upload" in data

    async def test_stats_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 401

    @patch("app.api.v1.dashboard.analytics_service")
    async def test_stats_empty_user(self, mock_service, client: AsyncClient, auth_headers):
        """New user with no data should return zeros, not errors."""
        mock_service.get_stats = AsyncMock(return_value={
            "total_resumes": 0,
            "total_analyses": 0,
            "total_jobs": 0,
            "total_cover_letters": 0,
            "average_ats_score": 0.0,
            "best_ats_score": 0.0,
            "last_upload": None,
        })
        resp = await client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_resumes"] == 0
        assert data["last_upload"] is None


class TestDashboardAnalytics:
    """GET /api/v1/dashboard/analytics"""

    @patch("app.api.v1.dashboard.analytics_service")
    async def test_analytics_structure(self, mock_service, client: AsyncClient, auth_headers):
        mock_service.get_analytics = AsyncMock(return_value={
            "score_trend": [
                {"date": "2026-07-01", "score": 68.0, "count": 2},
                {"date": "2026-07-10", "score": 74.5, "count": 1},
                {"date": "2026-07-15", "score": 81.0, "count": 3},
            ],
            "component_averages": {
                "keyword_match": 72.0,
                "formatting": 80.0,
                "section_completeness": 75.0,
                "skills_match": 68.0,
                "experience_relevance": 70.0,
            },
            "top_matched_jobs": [
                {"job_title": "Senior Dev", "company": "TechCorp", "score": 82.0, "analysis_id": "abc"},
            ],
            "period_days": 30,
        })
        resp = await client.get("/api/v1/dashboard/analytics?days=30", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "score_trend" in data
        assert "component_averages" in data
        assert "top_matched_jobs" in data
        assert len(data["score_trend"]) == 3
        assert data["component_averages"]["keyword_match"] == pytest.approx(72.0, rel=0.01)

    @patch("app.api.v1.dashboard.analytics_service")
    async def test_analytics_days_param(self, mock_service, client: AsyncClient, auth_headers):
        mock_service.get_analytics = AsyncMock(return_value={
            "score_trend": [], "component_averages": {}, "top_matched_jobs": [], "period_days": 90
        })
        resp = await client.get("/api/v1/dashboard/analytics?days=90", headers=auth_headers)
        assert resp.status_code == 200

    async def test_analytics_invalid_days(self, client: AsyncClient, auth_headers):
        """days < 7 or > 365 should be rejected."""
        resp = await client.get("/api/v1/dashboard/analytics?days=2", headers=auth_headers)
        assert resp.status_code == 422

    async def test_analytics_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/analytics")
        assert resp.status_code == 401


class TestDashboardActivity:
    """GET /api/v1/dashboard/activity"""

    @patch("app.api.v1.dashboard.analytics_service")
    async def test_activity_structure(self, mock_service, client: AsyncClient, auth_headers):
        mock_service.get_activity = AsyncMock(return_value={
            "activities": [
                {
                    "type": "resume_uploaded",
                    "description": "Uploaded resume.pdf",
                    "timestamp": "2026-07-19T10:00:00Z",
                    "metadata": {"resume_id": "abc", "status": "completed"},
                },
                {
                    "type": "ats_analysis_completed",
                    "description": "ATS score: 78 for Senior Dev at TechCorp",
                    "timestamp": "2026-07-19T10:05:00Z",
                    "metadata": {"analysis_id": "def", "score": 78.0},
                },
            ]
        })
        resp = await client.get("/api/v1/dashboard/activity", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "activities" in data
        assert len(data["activities"]) == 2
        first = data["activities"][0]
        assert "type" in first
        assert "description" in first
        assert "timestamp" in first

    @patch("app.api.v1.dashboard.analytics_service")
    async def test_activity_limit_param(self, mock_service, client: AsyncClient, auth_headers):
        mock_service.get_activity = AsyncMock(return_value={"activities": []})
        resp = await client.get("/api/v1/dashboard/activity?limit=5", headers=auth_headers)
        assert resp.status_code == 200

    async def test_activity_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/dashboard/activity")
        assert resp.status_code == 401

    @patch("app.api.v1.dashboard.analytics_service")
    async def test_activity_empty(self, mock_service, client: AsyncClient, auth_headers):
        """New user with no activity returns empty list, not error."""
        mock_service.get_activity = AsyncMock(return_value={"activities": []})
        resp = await client.get("/api/v1/dashboard/activity", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["activities"] == []
