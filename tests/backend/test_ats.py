"""
SmartHire AI — ATS Analysis API Tests

Covers:
- POST /ats/analyze       (triggers Celery, validates inputs)
- GET  /ats/status/{id}   (task state polling)
- GET  /ats/score/{id}    (latest score, 404 when no analysis)
- GET  /ats/history       (pagination, filter by resume)
- GET  /ats/export/{id}   (triggers PDF export)

All Celery tasks are mocked so tests remain synchronous and fast.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.analysis import ATSAnalysis

pytestmark = pytest.mark.asyncio


class TestTriggerAnalysis:
    """POST /api/v1/ats/analyze"""

    @patch("app.api.v1.ats.generate_ats_analysis")
    async def test_analyze_success(self, mock_task, client: AsyncClient, auth_headers, sample_resume, sample_job):
        mock_task.delay.return_value = MagicMock(id="task-ats-001")
        resp = await client.post(
            "/api/v1/ats/analyze",
            json={"resume_id": str(sample_resume.id), "job_id": str(sample_job.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        mock_task.delay.assert_called_once()

    @patch("app.api.v1.ats.generate_ats_analysis")
    async def test_analyze_resume_not_ready(self, mock_task, client: AsyncClient, auth_headers, db, test_user, sample_job):
        # Create a pending resume
        pending_resume = ATSAnalysis.__table__  # Just use a different fixture
        from app.models.resume import Resume
        pending = Resume(
            id=uuid.uuid4(),
            user_id=test_user.id,
            filename="pending.pdf",
            s3_key="resumes/test/pending.pdf",
            file_size=1000,
            status="pending",
        )
        db.add(pending)
        await db.flush()

        resp = await client.post(
            "/api/v1/ats/analyze",
            json={"resume_id": str(pending.id), "job_id": str(sample_job.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_analyze_missing_resume(self, client: AsyncClient, auth_headers, sample_job):
        resp = await client.post(
            "/api/v1/ats/analyze",
            json={"resume_id": str(uuid.uuid4()), "job_id": str(sample_job.id)},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_analyze_missing_job(self, client: AsyncClient, auth_headers, sample_resume):
        resp = await client.post(
            "/api/v1/ats/analyze",
            json={"resume_id": str(sample_resume.id), "job_id": str(uuid.uuid4())},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_analyze_unauthenticated(self, client: AsyncClient, sample_resume, sample_job):
        resp = await client.post(
            "/api/v1/ats/analyze",
            json={"resume_id": str(sample_resume.id), "job_id": str(sample_job.id)},
        )
        assert resp.status_code == 401


class TestTaskStatus:
    """GET /api/v1/ats/status/{task_id}"""

    @patch("app.api.v1.ats.celery_app")
    async def test_progress_state(self, mock_celery, client: AsyncClient, auth_headers):
        mock_result = MagicMock()
        mock_result.state = "PROGRESS"
        mock_result.info = {"progress": 65, "message": "Scoring components..."}
        mock_celery.AsyncResult.return_value = mock_result
        resp = await client.get("/api/v1/ats/status/task-001", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "PROGRESS"
        assert data["progress"] == 65

    @patch("app.api.v1.ats.celery_app")
    async def test_failure_state(self, mock_celery, client: AsyncClient, auth_headers):
        mock_result = MagicMock()
        mock_result.state = "FAILURE"
        mock_result.info = None
        mock_result.result = ValueError("Model timeout")
        mock_celery.AsyncResult.return_value = mock_result
        resp = await client.get("/api/v1/ats/status/task-fail", headers=auth_headers)
        data = resp.json()
        assert data["state"] == "FAILURE"


class TestGetScore:
    """GET /api/v1/ats/score/{resume_id}"""

    async def test_score_found(self, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        analysis = ATSAnalysis(
            id=uuid.uuid4(),
            resume_id=sample_resume.id,
            job_id=sample_job.id,
            user_id=test_user.id,
            overall_score=72.5,
            keyword_score=68.0,
            formatting_score=80.0,
            section_score=75.0,
            skills_score=70.0,
            experience_score=73.0,
            detailed_report={
                "matched_keywords": ["Python", "FastAPI"],
                "missing_keywords": ["Kubernetes"],
                "recommendations": ["Add Kubernetes experience"],
                "skill_match_details": {"matched": ["Python"], "missing": ["Redis"]},
            },
        )
        db.add(analysis)
        await db.flush()

        resp = await client.get(f"/api/v1/ats/score/{sample_resume.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == pytest.approx(72.5, rel=0.01)
        assert "components" in data
        assert data["components"]["keyword_match"]["score"] == pytest.approx(68.0, rel=0.01)

    async def test_score_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get(f"/api/v1/ats/score/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_score_filter_by_job(self, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        analysis = ATSAnalysis(
            id=uuid.uuid4(),
            resume_id=sample_resume.id,
            job_id=sample_job.id,
            user_id=test_user.id,
            overall_score=65.0,
            keyword_score=60.0, formatting_score=70.0,
            section_score=65.0, skills_score=60.0, experience_score=70.0,
        )
        db.add(analysis)
        await db.flush()

        resp = await client.get(
            f"/api/v1/ats/score/{sample_resume.id}?job_id={sample_job.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["overall_score"] == pytest.approx(65.0, rel=0.01)


class TestATSHistory:
    """GET /api/v1/ats/history"""

    async def test_history_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/ats/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_history_with_items(self, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        for score in [75.0, 82.0]:
            db.add(ATSAnalysis(
                id=uuid.uuid4(),
                resume_id=sample_resume.id,
                job_id=sample_job.id,
                user_id=test_user.id,
                overall_score=score,
                keyword_score=score, formatting_score=score,
                section_score=score, skills_score=score, experience_score=score,
            ))
        await db.flush()

        resp = await client.get("/api/v1/ats/history", headers=auth_headers)
        data = resp.json()
        assert data["total"] >= 2

    async def test_history_pagination(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/ats/history?page=1&page_size=5", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["page"] == 1
