"""
SmartHire AI — Cover Letter API Tests

Covers:
- POST /cover-letter/generate  (dispatches Celery task)
- GET  /cover-letter/status    (polling)
- GET  /cover-letter/list      (pagination)
- GET  /cover-letter/{id}      (found, 404)
- PUT  /cover-letter/{id}      (update content)
- GET  /cover-letter/{id}/export (PDF generation + S3 URL)
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.cover_letter import CoverLetter

pytestmark = pytest.mark.asyncio


class TestGenerateCoverLetter:
    """POST /api/v1/cover-letter/generate"""

    @patch("app.api.v1.cover_letter.generate_cover_letter_task")
    async def test_generate_success(self, mock_task, client: AsyncClient, auth_headers, sample_resume, sample_job):
        mock_task.delay.return_value = MagicMock(id="task-cl-001")
        resp = await client.post("/api/v1/cover-letter/generate", json={
            "resume_id": str(sample_resume.id),
            "job_id": str(sample_job.id),
            "tone": "professional",
            "word_limit": 400,
            "highlights": ["5 years Python experience"],
        }, headers=auth_headers)
        assert resp.status_code == 202
        data = resp.json()
        assert "letter_id" in data
        assert "task_id" in data
        mock_task.delay.assert_called_once()

    @patch("app.api.v1.cover_letter.generate_cover_letter_task")
    async def test_generate_invalid_tone_rejected(self, mock_task, client: AsyncClient, auth_headers, sample_resume, sample_job):
        resp = await client.post("/api/v1/cover-letter/generate", json={
            "resume_id": str(sample_resume.id),
            "job_id": str(sample_job.id),
            "tone": "sarcastic",  # invalid tone
            "word_limit": 400,
        }, headers=auth_headers)
        assert resp.status_code == 422

    async def test_generate_missing_resume(self, client: AsyncClient, auth_headers, sample_job):
        resp = await client.post("/api/v1/cover-letter/generate", json={
            "resume_id": str(uuid.uuid4()),
            "job_id": str(sample_job.id),
            "tone": "professional",
        }, headers=auth_headers)
        assert resp.status_code == 404

    async def test_generate_unauthenticated(self, client: AsyncClient, sample_resume, sample_job):
        resp = await client.post("/api/v1/cover-letter/generate", json={
            "resume_id": str(sample_resume.id),
            "job_id": str(sample_job.id),
            "tone": "professional",
        })
        assert resp.status_code == 401


class TestTaskStatus:
    """GET /api/v1/cover-letter/status/{task_id}"""

    @patch("app.api.v1.cover_letter.celery_app")
    async def test_pending_status(self, mock_celery, client: AsyncClient, auth_headers):
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.info = {}
        mock_celery.AsyncResult.return_value = mock_result
        resp = await client.get("/api/v1/cover-letter/status/task-cl-001", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["state"] == "PENDING"


class TestListCoverLetters:
    """GET /api/v1/cover-letter/list"""

    async def test_list_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/cover-letter/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert data["total"] == 0

    async def test_list_with_items(self, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        letter = CoverLetter(
            id=uuid.uuid4(),
            user_id=test_user.id,
            resume_id=sample_resume.id,
            job_id=sample_job.id,
            content="Dear Hiring Manager, I am excited to apply...",
            tone="professional",
        )
        db.add(letter)
        await db.flush()
        resp = await client.get("/api/v1/cover-letter/list", headers=auth_headers)
        data = resp.json()
        assert data["total"] >= 1


class TestGetCoverLetter:
    """GET /api/v1/cover-letter/{letter_id}"""

    async def test_get_existing(self, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        letter = CoverLetter(
            id=uuid.uuid4(),
            user_id=test_user.id,
            resume_id=sample_resume.id,
            job_id=sample_job.id,
            content="Dear Hiring Manager, I am writing to express my interest...",
            tone="confident",
        )
        db.add(letter)
        await db.flush()
        resp = await client.get(f"/api/v1/cover-letter/{letter.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(letter.id)
        assert data["tone"] == "confident"
        assert "Dear Hiring Manager" in data["content"]

    async def test_get_nonexistent(self, client: AsyncClient, auth_headers):
        resp = await client.get(f"/api/v1/cover-letter/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateCoverLetter:
    """PUT /api/v1/cover-letter/{letter_id}"""

    async def test_update_content(self, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        letter = CoverLetter(
            id=uuid.uuid4(),
            user_id=test_user.id,
            resume_id=sample_resume.id,
            job_id=sample_job.id,
            content="Original content.",
            tone="professional",
        )
        db.add(letter)
        await db.flush()
        resp = await client.put(
            f"/api/v1/cover-letter/{letter.id}",
            json={"content": "Updated content that is much better and now meets the minimum length requirement."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "Updated content that is much better and now meets the minimum length requirement."

    async def test_update_clears_s3_key(self, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        """Editing content should invalidate any cached PDF export."""
        letter = CoverLetter(
            id=uuid.uuid4(),
            user_id=test_user.id,
            resume_id=sample_resume.id,
            job_id=sample_job.id,
            content="Original content.",
            tone="professional",
            s3_key="cover-letters/user/old_export.pdf",
        )
        db.add(letter)
        await db.flush()
        resp = await client.put(
            f"/api/v1/cover-letter/{letter.id}",
            json={"content": "Edited content that is now long enough to pass the minimum validation check."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["s3_key"] is None


class TestExportCoverLetter:
    """GET /api/v1/cover-letter/{letter_id}/export"""

    @patch("app.api.v1.cover_letter.pdf_export_service")
    async def test_export_generates_pdf(self, mock_pdf, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        mock_pdf.export_cover_letter.return_value = (
            "cover-letters/user/letter.pdf",
            "https://blob.vercel-storage.com/bucket/letter.pdf?token=abc",
        )
        letter = CoverLetter(
            id=uuid.uuid4(),
            user_id=test_user.id,
            resume_id=sample_resume.id,
            job_id=sample_job.id,
            content="Dear Hiring Manager, this is my complete cover letter. " * 10,
            tone="professional",
        )
        db.add(letter)
        await db.flush()
        resp = await client.get(f"/api/v1/cover-letter/{letter.id}/export", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "download_url" in data
        assert "blob.vercel-storage.com" in data["download_url"]

    async def test_export_empty_content_rejected(self, client: AsyncClient, auth_headers, db, test_user, sample_resume, sample_job):
        letter = CoverLetter(
            id=uuid.uuid4(),
            user_id=test_user.id,
            resume_id=sample_resume.id,
            job_id=sample_job.id,
            content="",  # Not ready yet
            tone="professional",
        )
        db.add(letter)
        await db.flush()
        resp = await client.get(f"/api/v1/cover-letter/{letter.id}/export", headers=auth_headers)
        assert resp.status_code == 409
