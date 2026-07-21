"""
SmartHire AI — Job Description API Router

Endpoints:
    POST   /job/create       Save a job description + parse with Gemini
    GET    /job/list         Paginated list of user's jobs
    GET    /job/{job_id}     Full job details
    DELETE /job/{job_id}     Delete a job
    POST   /job/match        Semantic match score: resume vs job
    GET    /job/skill-gap    Detailed skill gap analysis
"""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.job import (
    JobCreate,
    JobMatchResponse,
    JobResponse,
    JobSummary,
    PaginatedJobs,
    SkillGapResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_job_or_404(db: AsyncSession, job_id: str, user_id: str) -> Job:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


async def _get_resume_or_404(db: AsyncSession, resume_id: str, user_id: str) -> Resume:
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return resume


async def _parse_job_in_background(job_id: str, description: str) -> None:
    """Parse job description with Gemini in background (called as BackgroundTask)."""
    import asyncio
    from app.core.database import AsyncSessionFactory
    from app.services.resume_parser import resume_parser
    from app.services.embedding_service import embedding_service

    try:
        parsed_data = resume_parser.extract_job_entities(description)

        async with AsyncSessionFactory() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.parsed_data = parsed_data
                job.required_skills = parsed_data.get("required_skills", [])
                await session.commit()

        # Also embed the job description for future similarity searches
        embedding_service.add_job(
            job_id=job_id,
            text=description,
            metadata={"job_id": job_id},
        )
        logger.info("Background job parsing complete", job_id=job_id)

    except Exception as e:
        logger.error("Background job parsing failed", job_id=job_id, error=str(e))


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/create",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a job description",
)
async def create_job(
    body: JobCreate,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """
    Save a job description and trigger background parsing with Gemini.

    The job is saved immediately with the raw description.
    Gemini entity extraction (required_skills, parsed_data) runs as a background task
    and updates the record within a few seconds.
    """
    job = Job(
        id=uuid.uuid4(),
        user_id=user_id,
        title=body.title,
        company=body.company,
        description=body.description,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Parse in background (non-blocking for the request)
    background_tasks.add_task(
        _parse_job_in_background,
        str(job.id),
        body.description,
    )

    logger.info("Job created", job_id=str(job.id), title=body.title, user_id=user_id)
    return JobResponse.model_validate(job)


@router.get(
    "/list",
    response_model=PaginatedJobs,
    summary="List user's saved job descriptions",
)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaginatedJobs:
    """Return a paginated list of the user's saved job descriptions."""
    offset = (page - 1) * page_size

    count_result = await db.execute(
        select(func.count(Job.id)).where(Job.user_id == user_id)
    )
    total = int(count_result.scalar() or 0)

    result = await db.execute(
        select(Job)
        .where(Job.user_id == user_id)
        .order_by(Job.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    jobs = result.scalars().all()

    return PaginatedJobs(
        items=[JobSummary.model_validate(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get a job description by ID",
)
async def get_job(
    job_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Retrieve a job description with parsed entities."""
    job = await _get_job_or_404(db, str(job_id), user_id)
    return JobResponse.model_validate(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job description",
)
async def delete_job(
    job_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a saved job description. Also removes its ChromaDB embedding."""
    job = await _get_job_or_404(db, str(job_id), user_id)

    try:
        from app.services.embedding_service import embedding_service
        embedding_service.delete_job(str(job_id))
    except Exception as e:
        logger.warning("ChromaDB delete failed for job", job_id=str(job_id), error=str(e))

    await db.delete(job)
    logger.info("Job deleted", job_id=str(job_id), user_id=user_id)


@router.post(
    "/match",
    response_model=JobMatchResponse,
    summary="Compute semantic match score between resume and job",
)
async def match_resume_to_job(
    resume_id: uuid.UUID,
    job_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> JobMatchResponse:
    """
    Compute a multi-dimensional match score between a resume and job description.

    Uses:
    - Cosine similarity between embeddings (semantic, 50%)
    - Direct skills overlap (35%)
    - Education match heuristic (15%)

    Returns a breakdown with matched/missing/bonus skills.
    """
    resume = await _get_resume_or_404(db, str(resume_id), user_id)
    job = await _get_job_or_404(db, str(job_id), user_id)

    if not resume.parsed_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resume must be fully processed before matching. Check resume status.",
        )

    from app.services.embedding_service import embedding_service
    from app.services.job_matcher import job_matcher

    resume_embedding = embedding_service.get_resume_embedding(str(resume_id))
    job_embedding = embedding_service.get_job_embedding(str(job_id))

    # Use parsed data or fall back to raw description
    job_parsed = job.parsed_data or {
        "title": job.title,
        "company": job.company,
        "required_skills": job.required_skills or [],
        "tech_stack": [],
        "nice_to_have_skills": [],
    }

    match_result = job_matcher.match(
        resume_parsed=resume.parsed_data,
        job_parsed=job_parsed,
        resume_embedding=resume_embedding,
        job_embedding=job_embedding,
    )

    return JobMatchResponse(
        resume_id=resume_id,
        job_id=job_id,
        **match_result,
    )


@router.get(
    "/skill-gap",
    response_model=SkillGapResponse,
    summary="Get detailed skill gap analysis",
)
async def get_skill_gap(
    resume_id: uuid.UUID = Query(..., description="Resume UUID"),
    job_id: uuid.UUID = Query(..., description="Job UUID"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SkillGapResponse:
    """
    Detailed skill gap analysis between a resume and job description.

    Returns:
    - Matched, missing (with learning resources), and bonus skills
    - Gap score (0 = perfect, 100 = all missing)
    - AI-generated learning recommendations
    """
    resume = await _get_resume_or_404(db, str(resume_id), user_id)
    job = await _get_job_or_404(db, str(job_id), user_id)

    if not resume.parsed_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resume must be processed before skill gap analysis",
        )

    from app.services.skill_gap_analyzer import skill_gap_analyzer

    job_parsed = job.parsed_data or {
        "title": job.title,
        "required_skills": job.required_skills or [],
        "tech_stack": [],
        "nice_to_have_skills": [],
        "seniority_level": "mid",
    }

    gap_result = skill_gap_analyzer.analyze(
        resume_parsed=resume.parsed_data,
        job_parsed=job_parsed,
    )

    return SkillGapResponse(
        resume_id=resume_id,
        job_id=job_id,
        matched_skills=gap_result["matched_skills"],
        missing_skills=gap_result["missing_skills"],
        bonus_skills=gap_result["bonus_skills"],
        gap_score=gap_result["gap_score"],
        recommendations=gap_result["recommendations"],
    )
