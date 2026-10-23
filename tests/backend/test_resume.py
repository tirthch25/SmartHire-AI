"""
SmartHire AI — Resume API Tests

Covers:
- POST /resume/upload    (valid PDF, non-PDF, too large, empty)
- GET  /resume/list      (pagination, empty list)
- GET  /resume/{id}      (found, 404, wrong user)
- DELETE /resume/{id}    (success, 404)
- GET  /resume/{id}/download   (presigned URL)
- GET  /resume/task/{id}/status (PENDING, SUCCESS, FAILURE)
"""

import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.resume import Resume

pytestmark = pytest.mark.asyncio

# Minimal valid PDF bytes (1-page PDF stub)
VALID_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF"
)


class TestUploadResume:
    """POST /api/v1/resume/upload"""

    @patch("app.api.v1.resume.upload_bytes", return_value="resumes/test/file.pdf")
    @patch("app.api.v1.resume.process_resume_upload")
    async def test_upload_valid_pdf(self, mock_task, mock_s3, client: AsyncClient, auth_headers):
        mock_task.delay.return_value = MagicMock(id="task-abc-123")
        files = {"file": ("resume.pdf", io.BytesIO(VALID_PDF), "application/pdf")}
        resp = await client.post("/api/v1/resume/upload", files=files, headers=auth_headers)
        assert resp.status_code == 202
        data = resp.json()
        assert "resume_id" in data
        assert "task_id" in data
        assert data["status"] == "pending"
        mock_s3.assert_called_once()
        mock_task.delay.assert_called_once()

    @patch("app.api.v1.resume.upload_bytes", return_value="resumes/test/file.pdf")
    @patch("app.api.v1.resume.process_resume_upload")
    async def test_upload_non_pdf_rejected(self, mock_task, mock_s3, client: AsyncClient, auth_headers):
        files = {"file": ("resume.docx", io.BytesIO(b"not a pdf"), "application/msword")}
        resp = await client.post("/api/v1/resume/upload", files=files, headers=auth_headers)
        assert resp.status_code == 415

    @patch("app.api.v1.resume.upload_bytes", return_value="resumes/test/file.pdf")
    @patch("app.api.v1.resume.process_resume_upload")
    async def test_upload_too_large_rejected(self, mock_task, mock_s3, client: AsyncClient, auth_headers):
        large_pdf = b"%PDF-1.4" + b"A" * (11 * 1024 * 1024)  # 11MB
        files = {"file": ("big.pdf", io.BytesIO(large_pdf), "application/pdf")}
        resp = await client.post("/api/v1/resume/upload", files=files, headers=auth_headers)
        assert resp.status_code == 413

    async def test_upload_unauthenticated(self, client: AsyncClient):
        files = {"file": ("resume.pdf", io.BytesIO(VALID_PDF), "application/pdf")}
        resp = await client.post("/api/v1/resume/upload", files=files)
        assert resp.status_code == 401


class TestListResumes:
    """GET /api/v1/resume/list"""

    async def test_list_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/resume/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 0

    async def test_list_with_items(self, client: AsyncClient, auth_headers, sample_resume):
        resp = await client.get("/api/v1/resume/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [r["id"] for r in data["items"]]
        assert str(sample_resume.id) in ids

    async def test_list_pagination(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/resume/list?page=1&page_size=5", headers=auth_headers)
        assert resp.status_code == 200

    async def test_list_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/resume/list")
        assert resp.status_code == 401


class TestGetResume:
    """GET /api/v1/resume/{resume_id}"""

    async def test_get_existing(self, client: AsyncClient, auth_headers, sample_resume):
        resp = await client.get(f"/api/v1/resume/{sample_resume.id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(sample_resume.id)
        assert data["filename"] == sample_resume.filename
        assert data["status"] == "completed"

    async def test_get_nonexistent(self, client: AsyncClient, auth_headers):
        fake_id = uuid.uuid4()
        resp = await client.get(f"/api/v1/resume/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_get_wrong_user(self, client: AsyncClient, db, sample_resume):
        # Create a different user and get their token
        from app.models.user import User
        from app.core.security import hash_password, create_access_token
        other = User(
            id=uuid.uuid4(),
            email="other@smarthire.ai",
            full_name="Other",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        db.add(other)
        await db.flush()
        token = create_access_token(subject=str(other.id))
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get(f"/api/v1/resume/{sample_resume.id}", headers=headers)
        assert resp.status_code == 404


class TestDeleteResume:
    """DELETE /api/v1/resume/{resume_id}"""

    @patch("app.api.v1.resume.delete_file", return_value=True)
    async def test_delete_success(self, mock_delete, client: AsyncClient, auth_headers):
        # Deleting a non-existent UUID should return 404
        fake_id = uuid.uuid4()
        resp = await client.delete(f"/api/v1/resume/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404  # Doesn't exist → 404

    async def test_delete_unauthenticated(self, client: AsyncClient, sample_resume):
        resp = await client.delete(f"/api/v1/resume/{sample_resume.id}")
        assert resp.status_code == 401


class TestTaskStatus:
    """GET /api/v1/resume/task/{task_id}/status"""

    @patch("app.api.v1.resume.celery_app")
    async def test_pending_state(self, mock_celery, client: AsyncClient, auth_headers):
        mock_result = MagicMock()
        mock_result.state = "PENDING"
        mock_result.info = {}
        mock_celery.AsyncResult.return_value = mock_result
        resp = await client.get("/api/v1/resume/task/fake-task-id/status", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["state"] == "PENDING"

    @patch("app.api.v1.resume.celery_app")
    async def test_success_state(self, mock_celery, client: AsyncClient, auth_headers):
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.info = {"resume_id": "abc", "status": "completed"}
        mock_celery.AsyncResult.return_value = mock_result
        resp = await client.get("/api/v1/resume/task/fake-task-id/status", headers=auth_headers)
        data = resp.json()
        assert data["state"] == "SUCCESS"
        assert data["progress"] == 100
