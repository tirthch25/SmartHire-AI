"""
SmartHire AI — Resume API Router

Endpoints:
    POST   /resume/upload              Upload PDF → S3 → Celery task
    GET    /resume/list                Paginated list of user's resumes
    GET    /resume/{resume_id}         Full resume with parsed data
    DELETE /resume/{resume_id}         Delete resume + S3 object
    GET    /resume/{resume_id}/download Presigned S3 download URL
"""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limiter import RATE_LIMIT_UPLOAD, limiter
from app.core.s3_client import build_resume_key, delete_file, generate_presigned_url, upload_bytes
from app.core.security import get_current_user_id
from app.models.resume import Resume
from app.schemas.resume import (
    DownloadUrlResponse,
    PaginatedResumes,
    ResumeResponse,
    ResumeSummary,
    ResumeUploadResponse,
    TaskStatusResponse,
)
from app.workers.celery_app import celery_app
from app.workers.tasks import process_resume_upload

logger = structlog.get_logger(__name__)

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_resume_or_404(
    db: AsyncSession, resume_id: str, user_id: str
) -> Resume:
    """Fetch a resume owned by the given user, or raise 404."""
    result = await db.execute(
        select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == user_id,
        )
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found",
        )
    return resume


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a PDF resume",
)
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_resume(
    request: Request,
    file: UploadFile = File(..., description="PDF file, max 10 MB"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ResumeUploadResponse:
    """
    Upload a PDF resume file.

    - Validates MIME type (must be application/pdf) and file size (max 10 MB)
    - Uploads the PDF to AWS S3
    - Creates a resume record in the database (status: pending)
    - Dispatches a Celery task to process the resume asynchronously
    - Returns a task_id for status polling via GET /ats/status/{task_id}
    """
    from app.core.config import settings

    # Validate content type
    if file.content_type not in settings.ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Only PDF files are accepted. Received: {file.content_type}",
        )

    # Read file bytes and validate size
    pdf_bytes = await file.read()
    file_size = len(pdf_bytes)

    if file_size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_mb:.0f} MB",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Build S3 key and upload
    safe_filename = (file.filename or "resume.pdf").replace(" ", "_")
    s3_key = build_resume_key(user_id, safe_filename)

    try:
        upload_bytes(pdf_bytes, s3_key, content_type="application/pdf")
    except RuntimeError as e:
        logger.error("S3 upload failed during resume upload", error=str(e), user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File storage service unavailable. Please try again.",
        )

    # Create resume record
    resume = Resume(
        id=uuid.uuid4(),
        user_id=user_id,
        filename=safe_filename,
        s3_key=s3_key,
        file_size=file_size,
        status="pending",
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)

    # Dispatch Celery task
    task = process_resume_upload.delay(str(resume.id))
    resume.celery_task_id = task.id
    await db.flush()

    logger.info(
        "Resume upload accepted",
        resume_id=str(resume.id),
        task_id=task.id,
        user_id=user_id,
        filename=safe_filename,
        size_kb=file_size // 1024,
    )

    return ResumeUploadResponse(
        resume_id=resume.id,
        task_id=task.id,
        status="pending",
        message="Resume uploaded successfully. Processing has started.",
    )


@router.get(
    "/list",
    response_model=PaginatedResumes,
    summary="List all resumes for the current user",
)
async def list_resumes(
    page: int = 1,
    page_size: int = 10,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResumes:
    """Return a paginated list of the user's uploaded resumes."""
    from app.core.config import settings

    page_size = min(page_size, settings.MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    # Total count
    count_result = await db.execute(
        select(func.count(Resume.id)).where(Resume.user_id == user_id)
    )
    total = int(count_result.scalar() or 0)

    # Paginated items
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    resumes = result.scalars().all()

    return PaginatedResumes(
        items=[ResumeSummary.model_validate(r) for r in resumes],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{resume_id}",
    response_model=ResumeResponse,
    summary="Get a resume with parsed data",
)
async def get_resume(
    resume_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """Retrieve a specific resume by ID, including all parsed entity data."""
    resume = await _get_resume_or_404(db, str(resume_id), user_id)
    return ResumeResponse.model_validate(resume)


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a resume",
)
async def delete_resume(
    resume_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a resume and its associated S3 file.
    Also removes the resume embedding from ChromaDB.
    """
    resume = await _get_resume_or_404(db, str(resume_id), user_id)

    # Delete from S3 (non-blocking — don't fail if S3 delete fails)
    try:
        delete_file(resume.s3_key)
    except Exception as e:
        logger.warning("S3 delete failed during resume deletion", key=resume.s3_key, error=str(e))

    # Delete embedding from ChromaDB
    try:
        from app.services.embedding_service import embedding_service
        embedding_service.delete_resume(str(resume_id))
    except Exception as e:
        logger.warning("ChromaDB delete failed", resume_id=str(resume_id), error=str(e))

    await db.delete(resume)
    logger.info("Resume deleted", resume_id=str(resume_id), user_id=user_id)


@router.get(
    "/{resume_id}/download",
    response_model=DownloadUrlResponse,
    summary="Get a presigned URL to download the original PDF",
)
async def download_resume(
    resume_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> DownloadUrlResponse:
    """Generate a temporary (1-hour) presigned URL for the original PDF file."""
    resume = await _get_resume_or_404(db, str(resume_id), user_id)

    try:
        url = generate_presigned_url(resume.s3_key)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate download URL",
        )

    return DownloadUrlResponse(download_url=url, expires_in=3600)


@router.get(
    "/task/{task_id}/status",
    response_model=TaskStatusResponse,
    summary="Poll Celery task status for resume processing",
)
async def get_task_status(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
) -> TaskStatusResponse:
    """Poll the status of an async resume processing task."""
    task_result = celery_app.AsyncResult(task_id)
    state = task_result.state
    meta = task_result.info or {}

    if state == "PENDING":
        return TaskStatusResponse(task_id=task_id, state="PENDING", progress=0, message="Waiting to start...")
    elif state == "PROGRESS":
        return TaskStatusResponse(
            task_id=task_id,
            state="PROGRESS",
            progress=meta.get("progress", 0),
            message=meta.get("message", "Processing..."),
        )
    elif state == "SUCCESS":
        return TaskStatusResponse(
            task_id=task_id,
            state="SUCCESS",
            progress=100,
            message="Complete",
            result=meta if isinstance(meta, dict) else {},
        )
    elif state == "FAILURE":
        return TaskStatusResponse(
            task_id=task_id,
            state="FAILURE",
            progress=0,
            message=str(meta) if meta else "Task failed",
        )
    else:
        return TaskStatusResponse(task_id=task_id, state=state, progress=0, message=str(meta))
