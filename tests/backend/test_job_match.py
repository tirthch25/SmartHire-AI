"""
SmartHire AI — Job Match & Skill Gap API Tests

Covers:
- POST /job/create      (success, validation)
- GET  /job/list        (pagination)
- GET  /job/{id}        (found, 404, wrong user)
- DELETE /job/{id}      (success, 404)
- POST /job/match       (semantic match scores)
- GET  /job/skill-gap   (gap analysis)
"""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

LONG_DESCRIPTION = (
    "We are seeking a Senior Python Developer with deep expertise in FastAPI, PostgreSQL, "
    "Redis, Docker, and AWS. You will lead backend development for a high-traffic SaaS platform. "
    "Strong knowledge of async Python, SQLAlchemy, and microservices architecture required. "
    "Experience with CI/CD pipelines, GitHub Actions, and cloud infrastructure is a plus. "
    "Minimum 5 years of professional Python experience."
)


class TestCreateJob:
    """POST /api/v1/job/create"""

    async def test_create_success(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/job/create", json={
            "title": "Software Engineer",
            "company": "Acme Corp",
            "description": LONG_DESCRIPTION,
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Software Engineer"
        assert data["company"] == "Acme Corp"
        assert "id" in data

    async def test_create_without_company(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/job/create", json={
            "title": "Data Scientist",
            "description": LONG_DESCRIPTION,
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["company"] is None

    async def test_create_short_description_rejected(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/job/create", json={
            "title": "Dev",
            "description": "Too short",
        }, headers=auth_headers)
        assert resp.status_code == 422

    async def test_create_missing_title(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/job/create", json={
            "description": LONG_DESCRIPTION,
        }, headers=auth_headers)
        assert resp.status_code == 422

    async def test_create_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/v1/job/create", json={
            "title": "Dev", "description": LONG_DESCRIPTION
        })
        assert resp.status_code == 401


class TestListJobs:
    """GET /api/v1/job/list"""

    async def test_list_with_items(self, client: AsyncClient, auth_headers, sample_job):
        resp = await client.get("/api/v1/job/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [j["id"] for j in data["items"]]
        assert str(sample_job.id) in ids

    async def test_list_pagination(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/job/list?page=1&page_size=5", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["page"] == 1
        assert resp.json()["page_size"] == 5


class TestGetJob:
    """GET /api/v1/job/{job_id}"""

    async def test_get_existing(self, client: AsyncClient, auth_headers, sample_job):
        resp = await client.get(f"/api/v1/job/{sample_job.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(sample_job.id)
        assert data["title"] == sample_job.title

    async def test_get_nonexistent(self, client: AsyncClient, auth_headers):
        resp = await client.get(f"/api/v1/job/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_wrong_user(self, client: AsyncClient, db, sample_job):
        from app.models.user import User
        from app.core.security import hash_password, create_access_token
        other = User(
            id=uuid.uuid4(), email="other2@smarthire.ai", full_name="Other",
            hashed_password=hash_password("Password123!"), is_active=True,
        )
        db.add(other)
        await db.flush()
        headers = {"Authorization": f"Bearer {create_access_token(subject=str(other.id))}"}
        resp = await client.get(f"/api/v1/job/{sample_job.id}", headers=headers)
        assert resp.status_code == 404


class TestDeleteJob:
    """DELETE /api/v1/job/{job_id}"""

    async def test_delete_nonexistent(self, client: AsyncClient, auth_headers):
        resp = await client.delete(f"/api/v1/job/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_delete_unauthenticated(self, client: AsyncClient, sample_job):
        resp = await client.delete(f"/api/v1/job/{sample_job.id}")
        assert resp.status_code == 401


class TestJobMatch:
    """POST /api/v1/job/match"""

    @patch("app.api.v1.job.embedding_service")
    @patch("app.api.v1.job.job_matcher")
    async def test_match_success(self, mock_matcher, mock_embedding, client: AsyncClient, auth_headers, sample_resume, sample_job):
        mock_embedding.get_resume_embedding.return_value = [0.1] * 384
        mock_embedding.get_job_embedding.return_value = [0.2] * 384
        mock_matcher.match.return_value = {
            "overall_match": 78.5,
            "semantic_score": 82.0,
            "skills_score": 75.0,
            "education_score": 80.0,
            "matched_skills": ["Python", "FastAPI"],
            "missing_skills": ["Redis"],
            "bonus_skills": [],
        }
        resp = await client.post(
            f"/api/v1/job/match?resume_id={sample_resume.id}&job_id={sample_job.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_match"] == pytest.approx(78.5, rel=0.01)
        assert "matched_skills" in data
        assert "missing_skills" in data

    async def test_match_resume_not_processed(self, client: AsyncClient, auth_headers, db, test_user, sample_job):
        from app.models.resume import Resume
        raw_resume = Resume(
            id=uuid.uuid4(), user_id=test_user.id,
            filename="raw.pdf", s3_key="resumes/test/raw.pdf",
            file_size=1000, status="pending",
        )
        db.add(raw_resume)
        await db.flush()
        resp = await client.post(
            f"/api/v1/job/match?resume_id={raw_resume.id}&job_id={sample_job.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 409


class TestSkillGap:
    """GET /api/v1/job/skill-gap"""

    @patch("app.api.v1.job.skill_gap_analyzer")
    async def test_skill_gap_success(self, mock_analyzer, client: AsyncClient, auth_headers, sample_resume, sample_job):
        mock_analyzer.analyze.return_value = {
            "matched_skills": ["Python", "FastAPI", "PostgreSQL"],
            "missing_skills": ["Redis", "Kubernetes"],
            "bonus_skills": ["Gemini API"],
            "gap_score": 28.0,
            "recommendations": [
                {"skill": "Redis", "resources": [{"title": "Redis docs", "url": "https://redis.io"}]}
            ],
        }
        resp = await client.get(
            f"/api/v1/job/skill-gap?resume_id={sample_resume.id}&job_id={sample_job.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "matched_skills" in data
        assert "missing_skills" in data
        assert "gap_score" in data
        assert data["gap_score"] == pytest.approx(28.0, rel=0.01)
