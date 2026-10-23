"""
SmartHire AI — ATS Scoring API Router

Endpoints:
    POST   /ats/analyze                Trigger ATS analysis (Celery) → task_id
    GET    /ats/status/{task_id}       Poll Celery task status
    GET    /ats/score/{resume_id}      Latest completed ATS score for a resume
    GET    /ats/history                Paginated ATS analysis history
    GET    /ats/export/{analysis_id}   Export ATS report as a private PDF download
"""

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.models.analysis import ATSAnalysis
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.analysis import (
    ATSAnalysisCreate,
    ATSAnalysisSummary,
    ATSAnalysisResponse,
    ATSComponentDetail,
    ATSScoreComponents,
    ExportUrlResponse,
    PaginatedAnalyses,
)
from app.schemas.resume import TaskStatusResponse
from app.workers.celery_app import celery_app
from app.workers.tasks import generate_ats_analysis

logger = structlog.get_logger(__name__)

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_analysis_or_404(
    db: AsyncSession, analysis_id: str, user_id: str
) -> ATSAnalysis:
    result = await db.execute(
        select(ATSAnalysis).where(
            ATSAnalysis.id == analysis_id,
            ATSAnalysis.user_id == user_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


def _build_analysis_response(analysis: ATSAnalysis) -> ATSAnalysisResponse:
    """Convert an ATSAnalysis ORM model to the full response schema."""
    components = ATSScoreComponents(
        keyword_match=ATSComponentDetail(
            score=analysis.keyword_score,
            weight=0.30,
            weighted=round(analysis.keyword_score * 0.30, 2),
        ),
        formatting=ATSComponentDetail(
            score=analysis.formatting_score,
            weight=0.15,
            weighted=round(analysis.formatting_score * 0.15, 2),
        ),
        section_completeness=ATSComponentDetail(
            score=analysis.section_score,
            weight=0.15,
            weighted=round(analysis.section_score * 0.15, 2),
        ),
        skills_match=ATSComponentDetail(
            score=analysis.skills_score,
            weight=0.20,
            weighted=round(analysis.skills_score * 0.20, 2),
        ),
        experience_relevance=ATSComponentDetail(
            score=analysis.experience_score,
            weight=0.20,
            weighted=round(analysis.experience_score * 0.20, 2),
        ),
    )

    return ATSAnalysisResponse(
        id=analysis.id,
        resume_id=analysis.resume_id,
        job_id=analysis.job_id,
        user_id=analysis.user_id,
        overall_score=analysis.overall_score,
        components=components,
        detailed_report=analysis.detailed_report,
        report_s3_key=analysis.report_s3_key,
        created_at=analysis.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger ATS analysis for a resume-job pair",
)
async def trigger_ats_analysis(
    body: ATSAnalysisCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Trigger an asynchronous ATS analysis for a resume against a job description.

    - Validates that the resume and job belong to the user
    - Dispatches the `generate_ats_analysis` Celery task
    - Returns a `task_id` for polling via GET /ats/status/{task_id}
    """
    # Validate resume ownership
    resume_result = await db.execute(
        select(Resume).where(
            Resume.id == str(body.resume_id),
            Resume.user_id == user_id,
        )
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    if resume.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Resume is not ready for analysis. Current status: {resume.status}",
        )

    # Validate job ownership
    job_result = await db.execute(
        select(Job).where(
            Job.id == str(body.job_id),
            Job.user_id == user_id,
        )
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Dispatch Celery task
    task = generate_ats_analysis.delay(
        str(body.resume_id),
        str(body.job_id),
        user_id,
    )

    logger.info(
        "ATS analysis triggered",
        resume_id=str(body.resume_id),
        job_id=str(body.job_id),
        task_id=task.id,
        user_id=user_id,
    )

    return {
        "task_id": task.id,
        "resume_id": str(body.resume_id),
        "job_id": str(body.job_id),
        "status": "pending",
        "message": "ATS analysis started. Poll /ats/status/{task_id} for progress.",
    }


@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
    summary="Poll ATS analysis task status",
)
async def get_task_status(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
) -> TaskStatusResponse:
    """Poll the status of an ATS analysis Celery task."""
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
            message=meta.get("message", "Analyzing..."),
        )
    elif state == "SUCCESS":
        return TaskStatusResponse(
            task_id=task_id,
            state="SUCCESS",
            progress=100,
            message="Analysis complete",
            result=meta if isinstance(meta, dict) else {},
        )
    elif state == "FAILURE":
        return TaskStatusResponse(
            task_id=task_id,
            state="FAILURE",
            progress=0,
            message=str(task_result.result) or "Analysis failed",
        )
    return TaskStatusResponse(task_id=task_id, state=state, progress=0)


@router.get(
    "/score/{resume_id}",
    response_model=ATSAnalysisResponse,
    summary="Get the latest ATS score for a resume",
)
async def get_ats_score(
    resume_id: uuid.UUID,
    job_id: Optional[uuid.UUID] = Query(None, description="Filter by specific job ID"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ATSAnalysisResponse:
    """
    Retrieve the latest completed ATS analysis for a resume.
    Optionally filter by job_id to get the analysis for a specific job.
    """
    query = (
        select(ATSAnalysis)
        .where(
            ATSAnalysis.resume_id == str(resume_id),
            ATSAnalysis.user_id == user_id,
        )
        .order_by(ATSAnalysis.created_at.desc())
    )

    if job_id:
        query = query.where(ATSAnalysis.job_id == str(job_id))

    result = await db.execute(query.limit(1))
    analysis = result.scalar_one_or_none()

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ATS analysis found for this resume. Run POST /ats/analyze first.",
        )

    return _build_analysis_response(analysis)


@router.get(
    "/history",
    response_model=PaginatedAnalyses,
    summary="List ATS analysis history",
)
async def list_ats_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    resume_id: Optional[uuid.UUID] = Query(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> PaginatedAnalyses:
    """Return paginated ATS analysis history for the current user."""
    offset = (page - 1) * page_size

    base_filter = [ATSAnalysis.user_id == user_id]
    if resume_id:
        base_filter.append(ATSAnalysis.resume_id == str(resume_id))

    count_result = await db.execute(
        select(func.count(ATSAnalysis.id)).where(*base_filter)
    )
    total = int(count_result.scalar() or 0)

    result = await db.execute(
        select(ATSAnalysis)
        .where(*base_filter)
        .order_by(ATSAnalysis.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    analyses = result.scalars().all()

    return PaginatedAnalyses(
        items=[ATSAnalysisSummary.model_validate(a) for a in analyses],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/export/{analysis_id}",
    response_model=ExportUrlResponse,
    summary="Export ATS analysis as a PDF report",
)
async def export_ats_report(
    analysis_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ExportUrlResponse:
    """
    Export an ATS analysis as a PDF report.

    If the report was already exported, returns the authenticated download route.
    Otherwise, triggers a Celery export task and waits for completion,
    or returns a task_id for polling if the task takes longer than expected.
    """
    analysis = await _get_analysis_or_404(db, str(analysis_id), user_id)

    # If already exported, return the authenticated download route.
    if analysis.report_s3_key:
        return ExportUrlResponse(
            download_url=f"/ats/export/{analysis.id}/file",
            expires_in=0,
        )

    # Dispatch export task
    from app.workers.tasks import export_pdf_report_task
    task = export_pdf_report_task.delay(str(analysis_id), user_id)

    logger.info("ATS PDF export task dispatched", analysis_id=str(analysis_id), task_id=task.id)

    # Return task_id so client can poll
    return ExportUrlResponse(
        download_url=f"/ats/status/{task.id}",
        expires_in=0,
    )


@router.get("/export/{analysis_id}/file", summary="Download the authenticated user's private ATS report")
async def download_ats_report(
    analysis_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    from app.core.blob_client import download_bytes

    analysis = await _get_analysis_or_404(db, str(analysis_id), user_id)
    if not analysis.report_s3_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    try:
        data = download_bytes(analysis.report_s3_key)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not download report") from e
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="ats-report-{analysis.id}.pdf"',
            "Cache-Control": "private, no-store",
        },
    )
