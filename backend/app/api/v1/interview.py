"""
SmartHire AI — Interview Question Generation API Router

Endpoints:
    POST   /interview/generate              Trigger Celery task → session_id + task_id
    GET    /interview/status/{task_id}      Poll Celery task status
    GET    /interview/{session_id}          Get generated questions
    GET    /interview/list                  List all interview sessions
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.interview_session import InterviewSession
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewSessionResponse,
    InterviewSessionSummary,
    PaginatedSessions,
    Question,
)
from app.schemas.resume import TaskStatusResponse
from app.workers.celery_app import celery_app
from app.workers.tasks import generate_interview_questions_task

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_session_or_404(
    db: AsyncSession, session_id: str, user_id: str
) -> InterviewSession:
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview session not found",
        )
    return session


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate interview questions for a resume-job pair",
)
async def generate_questions(
    body: InterviewSessionCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate AI-powered interview questions for a resume-job pair.

    - Creates an InterviewSession record (status: pending)
    - Dispatches Celery task for Gemini question generation
    - Returns session_id and task_id for polling

    Categories generated: Technical, Behavioral, Situational, Culture Fit
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
            detail="Resume must be fully processed before generating interview questions",
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

    # Create session record
    session = InterviewSession(
        id=uuid.uuid4(),
        user_id=user_id,
        resume_id=body.resume_id,
        job_id=body.job_id,
        questions=[],
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # Dispatch Celery task
    task = generate_interview_questions_task.delay(
        session_id=str(session.id),
        resume_id=str(body.resume_id),
        job_id=str(body.job_id),
        focus_areas=body.focus_areas,
        difficulty=body.difficulty,
        question_count=body.question_count,
    )

    session.celery_task_id = task.id
    await db.flush()

    logger.info(
        "Interview generation task dispatched",
        session_id=str(session.id),
        task_id=task.id,
        user_id=user_id,
    )

    return {
        "session_id": str(session.id),
        "task_id": task.id,
        "status": "pending",
        "message": f"Generating {body.question_count} interview questions. Poll /interview/status/{task.id}",
    }


@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Poll interview question generation task status",
)
async def get_task_status(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
) -> TaskStatusResponse:
    """Poll Celery task status for interview question generation."""
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
            message=meta.get("message", "Generating questions..."),
        )
    elif state == "SUCCESS":
        return TaskStatusResponse(
            task_id=task_id,
            state="SUCCESS",
            progress=100,
            message="Questions generated",
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
    response_model=PaginatedSessions,
    summary="List all interview sessions",
)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaginatedSessions:
    """Return a paginated list of all interview sessions for the current user."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(InterviewSession.id)).where(
            InterviewSession.user_id == user_id
        )
    )
    total = int(count_result.scalar() or 0)

    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id)
        .order_by(InterviewSession.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        items.append(
            InterviewSessionSummary(
                id=s.id,
                job_id=s.job_id,
                question_count=len(s.questions) if s.questions else 0,
                created_at=s.created_at,
            )
        )

    return PaginatedSessions(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/{session_id}",
    response_model=InterviewSessionResponse,
    summary="Get generated interview questions",
)
async def get_session(
    session_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionResponse:
    """
    Retrieve a completed interview session with all generated questions.

    If questions are still being generated, the questions list will be empty.
    """
    session = await _get_session_or_404(db, str(session_id), user_id)

    questions = [Question(**q) for q in (session.questions or [])]

    return InterviewSessionResponse(
        id=session.id,
        user_id=session.user_id,
        resume_id=session.resume_id,
        job_id=session.job_id,
        questions=questions,
        question_count=len(questions),
        created_at=session.created_at,
    )
