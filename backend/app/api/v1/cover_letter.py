"""
SmartHire AI — Cover Letter API Router

Endpoints:
    POST   /cover-letter/generate              Trigger Celery task → letter_id + task_id
    GET    /cover-letter/status/{task_id}      Poll task status
    GET    /cover-letter/list                  List user's cover letters
    GET    /cover-letter/{letter_id}           Get a cover letter
    PUT    /cover-letter/{letter_id}           Update/edit a cover letter
    GET    /cover-letter/{letter_id}/export    Export as PDF (S3 presigned URL)
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.blob_client import generate_presigned_url
from app.core.security import get_current_user_id
from app.models.cover_letter import CoverLetter
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.cover_letter import (
    CoverLetterCreate,
    CoverLetterExportResponse,
    CoverLetterResponse,
    CoverLetterSummary,
    CoverLetterUpdate,
    PaginatedCoverLetters,
)
from app.schemas.resume import TaskStatusResponse
from app.workers.celery_app import celery_app
from app.workers.tasks import generate_cover_letter_task

logger = structlog.get_logger(__name__)

router = APIRouter()

# Service reference (lazy loaded or patched in tests)
pdf_export_service = None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_letter_or_404(
    db: AsyncSession, letter_id: str, user_id: str
) -> CoverLetter:
    result = await db.execute(
        select(CoverLetter).where(
            CoverLetter.id == letter_id,
            CoverLetter.user_id == user_id,
        )
    )
    letter = result.scalar_one_or_none()
    if not letter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cover letter not found",
        )
    return letter


def _letter_to_response(letter: CoverLetter) -> CoverLetterResponse:
    return CoverLetterResponse(
        id=letter.id,
        user_id=letter.user_id,
        resume_id=letter.resume_id,
        job_id=letter.job_id,
        content=letter.content,
        tone=letter.tone,
        word_count=letter.word_count,
        s3_key=letter.s3_key,
        created_at=letter.created_at,
        updated_at=letter.updated_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate a personalized cover letter",
)
async def generate_cover_letter(
    body: CoverLetterCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate a personalized cover letter using Gemini AI.

    - Validates resume and job ownership
    - Creates a CoverLetter record (content: empty, pending)
    - Dispatches Celery task for Gemini generation
    - Returns letter_id + task_id for polling
    """
    # Validate resume
    resume_result = await db.execute(
        select(Resume).where(
            Resume.id == str(body.resume_id),
            Resume.user_id == user_id,
        )
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    if not resume.parsed_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resume must be fully processed before generating a cover letter",
        )

    # Validate job
    job_result = await db.execute(
        select(Job).where(
            Job.id == str(body.job_id),
            Job.user_id == user_id,
        )
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Create placeholder record
    letter = CoverLetter(
        id=uuid.uuid4(),
        user_id=user_id,
        resume_id=body.resume_id,
        job_id=body.job_id,
        content="",          # Will be populated by Celery task
        tone=body.tone,
    )
    db.add(letter)
    await db.flush()
    await db.refresh(letter)

    # Dispatch Celery task
    task = generate_cover_letter_task.delay(
        letter_id=str(letter.id),
        resume_id=str(body.resume_id),
        job_id=str(body.job_id),
        user_id=user_id,
        tone=body.tone,
        highlights=body.highlights,
        word_limit=body.word_limit,
    )

    letter.celery_task_id = task.id
    await db.flush()

    logger.info(
        "Cover letter generation dispatched",
        letter_id=str(letter.id),
        task_id=task.id,
        user_id=user_id,
    )

    return {
        "letter_id": str(letter.id),
        "task_id": task.id,
        "status": "pending",
        "message": f"Cover letter generation started. Poll /cover-letter/status/{task.id}",
    }


@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Poll cover letter generation task status",
)
async def get_task_status(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
) -> TaskStatusResponse:
    """Poll the status of a cover letter generation Celery task."""
    task_result = celery_app.AsyncResult(task_id)
    state = task_result.state
    meta = task_result.info or {}

    if state == "PENDING":
        return TaskStatusResponse(task_id=task_id, state="PENDING", progress=0, message="Queued...")
    elif state == "PROGRESS":
        return TaskStatusResponse(
            task_id=task_id,
            state="PROGRESS",
            progress=meta.get("progress", 0),
            message=meta.get("message", "Writing cover letter..."),
        )
    elif state == "SUCCESS":
        return TaskStatusResponse(
            task_id=task_id,
            state="SUCCESS",
            progress=100,
            message="Cover letter ready",
            result=meta if isinstance(meta, dict) else {},
        )
    elif state == "FAILURE":
        return TaskStatusResponse(
            task_id=task_id,
            state="FAILURE",
            progress=0,
            message=str(task_result.result) or "Generation failed",
        )
    return TaskStatusResponse(task_id=task_id, state=state, progress=0)


@router.get(
    "/list",
    response_model=PaginatedCoverLetters,
    summary="List user's cover letters",
)
async def list_cover_letters(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaginatedCoverLetters:
    """Return a paginated list of the user's generated cover letters."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(CoverLetter.id)).where(CoverLetter.user_id == user_id)
    )
    total = int(count_result.scalar() or 0)

    result = await db.execute(
        select(CoverLetter)
        .where(CoverLetter.user_id == user_id)
        .order_by(CoverLetter.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    letters = result.scalars().all()

    items = [
        CoverLetterSummary(
            id=l.id,
            job_id=l.job_id,
            tone=l.tone,
            word_count=l.word_count,
            created_at=l.created_at,
        )
        for l in letters
    ]

    return PaginatedCoverLetters(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{letter_id}",
    response_model=CoverLetterResponse,
    summary="Get a cover letter",
)
async def get_cover_letter(
    letter_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CoverLetterResponse:
    """Retrieve a specific cover letter by ID."""
    letter = await _get_letter_or_404(db, str(letter_id), user_id)
    return _letter_to_response(letter)


@router.put(
    "/{letter_id}",
    response_model=CoverLetterResponse,
    summary="Update/edit a cover letter",
)
async def update_cover_letter(
    letter_id: uuid.UUID,
    body: CoverLetterUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CoverLetterResponse:
    """
    Update the content of a cover letter (manual editing after AI generation).
    Invalidates the existing exported PDF (s3_key is cleared on content change).
    """
    letter = await _get_letter_or_404(db, str(letter_id), user_id)
    letter.content = body.content
    letter.s3_key = None  # Invalidate any previously exported PDF

    await db.flush()
    await db.refresh(letter)

    logger.info("Cover letter updated", letter_id=str(letter_id), user_id=user_id)
    return _letter_to_response(letter)


@router.get(
    "/{letter_id}/export",
    response_model=CoverLetterExportResponse,
    summary="Export cover letter as PDF",
)
async def export_cover_letter(
    letter_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> CoverLetterExportResponse:
    """
    Export a cover letter as a PDF file.

    If already exported, returns a fresh presigned URL for the existing PDF.
    Otherwise, generates a new PDF, uploads to S3, stores the key, and returns the URL.
    """
    letter = await _get_letter_or_404(db, str(letter_id), user_id)

    if not letter.content:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cover letter content is not ready yet. Check task status.",
        )

    # Return existing export if available
    if letter.s3_key:
        try:
            url = generate_presigned_url(letter.s3_key)
            return CoverLetterExportResponse(download_url=url, expires_in=3600)
        except Exception:
            pass  # S3 key may be stale — regenerate

    # Fetch job info for PDF header
    job_title = None
    company = None
    if letter.job_id:
        job_result = await db.execute(select(Job).where(Job.id == str(letter.job_id)))
        job = job_result.scalar_one_or_none()
        if job:
            job_title = job.title
            company = job.company

    # Generate PDF synchronously (fast enough for direct response)
    global pdf_export_service
    if pdf_export_service is None:
        from app.services.pdf_export_service import pdf_export_service as _pes
        pdf_export_service = _pes

    try:
        s3_key, download_url = pdf_export_service.export_cover_letter(
            content=letter.content,
            user_id=user_id,
            letter_id=str(letter_id),
            job_title=job_title,
            company=company,
        )
        letter.s3_key = s3_key
        await db.flush()

        logger.info("Cover letter PDF exported", letter_id=str(letter_id), s3_key=s3_key)
        return CoverLetterExportResponse(download_url=download_url, expires_in=3600)

    except Exception as e:
        logger.error("Cover letter PDF export failed", letter_id=str(letter_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDF export failed. Please try again.",
        )
