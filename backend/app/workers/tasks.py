"""
SmartHire AI — Celery Task Definitions

Five async tasks that handle all AI-heavy, long-running operations:

1. process_resume_upload   — PDF text extraction + Gemini parsing + ChromaDB embedding
2. generate_ats_analysis   — Full 5-component ATS scoring
3. generate_cover_letter_task  — Gemini cover letter generation
4. generate_interview_questions_task — Gemini interview question generation
5. export_pdf_report_task  — ReportLab PDF generation + S3 upload

All tasks:
- Update their state (PROGRESS) for frontend polling
- Handle errors with structured logging
- Retry on transient failures (max 3 attempts)
- Store results in Redis result backend

Task states: PENDING → PROGRESS → SUCCESS | FAILURE
"""

import uuid
from typing import Optional

import structlog
from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)
structlog_logger = structlog.get_logger(__name__)


# ── Synchronous DB session for Celery (not async) ────────────────────────────
def _get_sync_session():
    """
    Create a synchronous SQLAlchemy session for use in Celery tasks.
    Celery workers do not run inside an async event loop.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings

    # Convert asyncpg URL to psycopg2 for sync usage
    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql://"
    ).replace("?sslmode=require", "")

    engine = create_engine(sync_url, pool_size=2, max_overflow=5, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _update_task_progress(task: Task, progress: int, message: str) -> None:
    """Update task state with progress percentage and message for frontend polling."""
    task.update_state(
        state="PROGRESS",
        meta={"progress": progress, "message": message},
    )


# ── Task 1: Process Resume Upload ─────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_resume_upload",
    max_retries=3,
    default_retry_delay=10,
    queue="resume",
)
def process_resume_upload(self: Task, resume_id: str) -> dict:
    """
    Full resume processing pipeline:
    1. Download PDF from S3 (10%)
    2. Extract text with pdfplumber (30%)
    3. Parse entities with Gemini (60%)
    4. Generate embedding + store in ChromaDB (80%)
    5. Update resume record in DB as 'completed' (100%)

    Args:
        resume_id: UUID string of the resume record.

    Returns:
        Dict with resume_id and extracted entity summary.
    """
    db = None
    try:
        from app.core.s3_client import download_bytes
        from app.models.resume import Resume
        from app.services.embedding_service import embedding_service
        from app.services.pdf_parser import pdf_parser
        from app.services.resume_parser import resume_parser

        db = _get_sync_session()

        # Mark as processing
        resume = db.execute(select(Resume).where(Resume.id == resume_id)).scalar_one()
        resume.status = "processing"
        resume.celery_task_id = self.request.id
        db.commit()

        _update_task_progress(self, 10, "Downloading PDF from S3...")
        logger.info(f"Processing resume {resume_id}")

        # Step 1: Download from S3
        pdf_bytes = download_bytes(resume.s3_key)

        _update_task_progress(self, 30, "Extracting text from PDF...")

        # Step 2: Parse PDF text
        parse_result = pdf_parser.parse(pdf_bytes)
        raw_text = parse_result.raw_text

        _update_task_progress(self, 55, "Analyzing resume with AI...")

        # Step 3: Extract entities with Gemini
        parsed_data = resume_parser.extract_resume_entities(raw_text)

        _update_task_progress(self, 75, "Building semantic embeddings...")

        # Step 4: Generate embedding and store in ChromaDB
        embedding = embedding_service.encode(raw_text)
        embedding_service.add_resume(
            resume_id=resume_id,
            text=raw_text,
            metadata={"user_id": str(resume.user_id)},
            embedding=embedding,
        )

        _update_task_progress(self, 90, "Saving results...")

        # Step 5: Update DB
        resume.raw_text = raw_text
        resume.parsed_data = parsed_data
        resume.status = "completed"
        db.commit()

        _update_task_progress(self, 100, "Resume processing complete!")

        logger.info(f"Resume {resume_id} processed successfully")
        return {
            "resume_id": resume_id,
            "status": "completed",
            "skills_count": len(parsed_data.get("skills", [])),
            "experience_count": len(parsed_data.get("experience", [])),
        }

    except Exception as exc:
        logger.error(f"Resume processing failed: {resume_id}", exc_info=exc)
        if db:
            try:
                resume = db.execute(select(Resume).where(Resume.id == resume_id)).scalar_one_or_none()
                if resume:
                    resume.status = "failed"
                    db.commit()
            except Exception:
                pass
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)

    finally:
        if db:
            db.close()


# ── Task 2: Generate ATS Analysis ─────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.generate_ats_analysis",
    max_retries=2,
    default_retry_delay=15,
    queue="ats",
)
def generate_ats_analysis(self: Task, resume_id: str, job_id: str, user_id: str) -> dict:
    """
    Full ATS scoring pipeline:
    1. Load resume + job from DB (10%)
    2. Get embeddings from ChromaDB (25%)
    3. Run 5-component scoring engine (75%)
    4. Store analysis in DB (100%)

    Args:
        resume_id: Resume UUID string.
        job_id: Job UUID string.
        user_id: User UUID string.

    Returns:
        Dict with analysis_id and overall_score.
    """
    db = None
    try:
        from app.models.analysis import ATSAnalysis
        from app.models.job import Job
        from app.models.resume import Resume
        from app.services.ats_scorer import ats_scorer
        from app.services.embedding_service import embedding_service
        from app.services.resume_parser import resume_parser

        db = _get_sync_session()

        _update_task_progress(self, 10, "Loading resume and job data...")

        resume = db.execute(select(Resume).where(Resume.id == resume_id)).scalar_one()
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one()

        if not resume.parsed_data:
            raise ValueError(f"Resume {resume_id} has not been parsed yet. Status: {resume.status}")

        # Parse job description if not already done
        if not job.parsed_data:
            _update_task_progress(self, 20, "Parsing job description...")
            job_parsed = resume_parser.extract_job_entities(job.description)
            job.required_skills = job_parsed.get("required_skills", [])
            job.parsed_data = job_parsed
            db.commit()
        else:
            job_parsed = job.parsed_data

        _update_task_progress(self, 30, "Loading semantic embeddings...")

        # Get embeddings (may be None if not yet stored)
        resume_embedding = embedding_service.get_resume_embedding(resume_id)
        job_embedding = embedding_service.get_job_embedding(job_id)

        # If job embedding not in ChromaDB, generate and store it
        if not job_embedding:
            _update_task_progress(self, 40, "Generating job embeddings...")
            job_embedding = embedding_service.add_job(
                job_id=job_id,
                text=job.description,
                metadata={"user_id": user_id, "title": job.title},
            )

        _update_task_progress(self, 50, "Computing ATS score components...")

        # Run scoring
        result = ats_scorer.score(
            resume_text=resume.raw_text or "",
            resume_parsed=resume.parsed_data,
            job_parsed=job_parsed,
            resume_embedding=resume_embedding,
            job_embedding=job_embedding,
        )

        _update_task_progress(self, 85, "Saving analysis results...")

        # Serialize components for JSONB storage
        components_dict = {
            k: {
                "score": v.score,
                "weight": v.weight,
                "weighted": v.weighted,
                "description": None,
            }
            for k, v in result.components.items()
        }

        analysis = ATSAnalysis(
            id=uuid.uuid4(),
            resume_id=resume_id,
            job_id=job_id,
            user_id=user_id,
            overall_score=result.overall_score,
            keyword_score=result.keyword_score,
            formatting_score=result.formatting_score,
            section_score=result.section_score,
            skills_score=result.skills_score,
            experience_score=result.experience_score,
            detailed_report=result.detailed_report,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        _update_task_progress(self, 100, "ATS analysis complete!")

        logger.info(
            f"ATS analysis complete for resume {resume_id}",
            overall=result.overall_score,
            analysis_id=str(analysis.id),
        )

        return {
            "analysis_id": str(analysis.id),
            "resume_id": resume_id,
            "job_id": job_id,
            "overall_score": result.overall_score,
        }

    except Exception as exc:
        logger.error(f"ATS analysis failed for resume {resume_id}", exc_info=exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 10)

    finally:
        if db:
            db.close()


# ── Task 3: Generate Cover Letter ─────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.generate_cover_letter_task",
    max_retries=2,
    default_retry_delay=10,
    queue="ai",
)
def generate_cover_letter_task(
    self: Task,
    letter_id: str,
    resume_id: str,
    job_id: str,
    user_id: str,
    tone: str = "professional",
    highlights: Optional[list] = None,
    word_limit: int = 400,
) -> dict:
    """
    Generate a personalized cover letter using Gemini.

    Args:
        letter_id: Pre-created CoverLetter UUID.
        resume_id: Resume UUID.
        job_id: Job UUID.
        user_id: User UUID.
        tone: Writing tone.
        highlights: Key points to emphasize.
        word_limit: Target word count.

    Returns:
        Dict with letter_id and word_count.
    """
    db = None
    try:
        from app.models.cover_letter import CoverLetter
        from app.models.job import Job
        from app.models.resume import Resume
        from app.services.cover_letter_generator import cover_letter_generator

        db = _get_sync_session()

        _update_task_progress(self, 20, "Loading resume and job data...")

        resume = db.execute(select(Resume).where(Resume.id == resume_id)).scalar_one()
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one()

        if not resume.parsed_data:
            raise ValueError(f"Resume {resume_id} must be processed before generating a cover letter")

        job_parsed = job.parsed_data or {"title": job.title, "company": job.company, "description": job.description}

        _update_task_progress(self, 50, "Generating cover letter with AI...")

        content = cover_letter_generator.generate(
            resume_parsed=resume.parsed_data,
            job_parsed=job_parsed,
            tone=tone,
            highlights=highlights or [],
            word_limit=word_limit,
        )

        _update_task_progress(self, 85, "Saving cover letter...")

        letter = db.execute(select(CoverLetter).where(CoverLetter.id == letter_id)).scalar_one()
        letter.content = content
        db.commit()

        _update_task_progress(self, 100, "Cover letter generated!")

        logger.info(f"Cover letter generated: {letter_id}", words=len(content.split()))
        return {"letter_id": letter_id, "word_count": len(content.split())}

    except Exception as exc:
        logger.error(f"Cover letter generation failed: {letter_id}", exc_info=exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 8)

    finally:
        if db:
            db.close()


# ── Task 4: Generate Interview Questions ──────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.generate_interview_questions_task",
    max_retries=2,
    default_retry_delay=10,
    queue="ai",
)
def generate_interview_questions_task(
    self: Task,
    session_id: str,
    resume_id: str,
    job_id: str,
    focus_areas: Optional[list] = None,
    difficulty: str = "medium",
    question_count: int = 15,
) -> dict:
    """
    Generate interview questions using Gemini.

    Args:
        session_id: Pre-created InterviewSession UUID.
        resume_id: Resume UUID.
        job_id: Job UUID.
        focus_areas: Areas to focus on.
        difficulty: Question difficulty.
        question_count: Number of questions.

    Returns:
        Dict with session_id and question_count.
    """
    db = None
    try:
        from app.models.interview_session import InterviewSession
        from app.models.job import Job
        from app.models.resume import Resume
        from app.services.interview_generator import interview_generator

        db = _get_sync_session()

        _update_task_progress(self, 20, "Loading resume and job data...")

        resume = db.execute(select(Resume).where(Resume.id == resume_id)).scalar_one()
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one()

        if not resume.parsed_data:
            raise ValueError(f"Resume {resume_id} must be processed first")

        job_parsed = job.parsed_data or {"title": job.title, "tech_stack": [], "seniority_level": "mid"}

        _update_task_progress(self, 50, "Generating interview questions with AI...")

        questions = interview_generator.generate(
            resume_parsed=resume.parsed_data,
            job_parsed=job_parsed,
            focus_areas=focus_areas or [],
            difficulty=difficulty,
            question_count=question_count,
        )

        _update_task_progress(self, 85, "Saving questions...")

        session = db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        ).scalar_one()
        session.questions = questions
        db.commit()

        _update_task_progress(self, 100, "Interview questions ready!")

        logger.info(f"Interview questions generated: {session_id}", count=len(questions))
        return {"session_id": session_id, "question_count": len(questions)}

    except Exception as exc:
        logger.error(f"Interview generation failed: {session_id}", exc_info=exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 8)

    finally:
        if db:
            db.close()


# ── Task 5: Export PDF Report ─────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    name="app.workers.tasks.export_pdf_report_task",
    max_retries=2,
    default_retry_delay=5,
    queue="export",
)
def export_pdf_report_task(self: Task, analysis_id: str, user_id: str) -> dict:
    """
    Generate and upload an ATS score report PDF to S3.

    Args:
        analysis_id: ATSAnalysis UUID.
        user_id: User UUID.

    Returns:
        Dict with analysis_id, s3_key, and download_url.
    """
    db = None
    try:
        from app.models.analysis import ATSAnalysis
        from app.services.pdf_export_service import pdf_export_service

        db = _get_sync_session()

        _update_task_progress(self, 25, "Loading analysis data...")

        analysis = db.execute(
            select(ATSAnalysis).where(ATSAnalysis.id == analysis_id)
        ).scalar_one()

        # Build data dict for PDF
        analysis_data = {
            "id": str(analysis.id),
            "overall_score": analysis.overall_score,
            "components": {
                "keyword_match": {"score": analysis.keyword_score, "weight": 0.30, "weighted": analysis.keyword_score * 0.30},
                "formatting": {"score": analysis.formatting_score, "weight": 0.15, "weighted": analysis.formatting_score * 0.15},
                "section_completeness": {"score": analysis.section_score, "weight": 0.15, "weighted": analysis.section_score * 0.15},
                "skills_match": {"score": analysis.skills_score, "weight": 0.20, "weighted": analysis.skills_score * 0.20},
                "experience_relevance": {"score": analysis.experience_score, "weight": 0.20, "weighted": analysis.experience_score * 0.20},
            },
            "detailed_report": analysis.detailed_report or {},
        }

        _update_task_progress(self, 50, "Generating PDF report...")

        s3_key, download_url = pdf_export_service.export_ats_report(
            analysis_data=analysis_data,
            user_id=user_id,
        )

        _update_task_progress(self, 90, "Saving S3 reference...")

        analysis.report_s3_key = s3_key
        db.commit()

        _update_task_progress(self, 100, "PDF report ready!")

        logger.info(f"ATS report exported: {analysis_id}", s3_key=s3_key)
        return {
            "analysis_id": analysis_id,
            "s3_key": s3_key,
            "download_url": download_url,
        }

    except Exception as exc:
        logger.error(f"PDF export failed: {analysis_id}", exc_info=exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)

    finally:
        if db:
            db.close()
