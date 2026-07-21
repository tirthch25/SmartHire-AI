"""
SmartHire AI — Analytics Service

Computes aggregated statistics for the dashboard.
All results are Redis-cached with configurable TTL.

Provides:
- Summary stats (counts, averages)
- Score trends over time (for line charts)
- Component averages (for radar/bar charts)
- Recent activity feed
- Top matched jobs
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import cache_get, cache_set
from app.models.analysis import ATSAnalysis
from app.models.cover_letter import CoverLetter
from app.models.interview_session import InterviewSession
from app.models.job import Job
from app.models.resume import Resume

logger = structlog.get_logger(__name__)


class AnalyticsService:
    """
    Aggregates user statistics for the dashboard.

    All methods accept an AsyncSession and user_id.
    Results are cached in Redis with 5-minute TTL.

    Usage:
        svc = AnalyticsService()
        stats = await svc.get_stats(db, user_id)
        analytics = await svc.get_analytics(db, user_id, days=30)
    """

    async def get_stats(self, db: AsyncSession, user_id: str) -> dict:
        """
        Get summary statistics for the user's dashboard.

        Returns:
            Dict with total counts, average scores, and last activity.
        """
        cache_key = f"cache:dashboard:{user_id}"
        cached = await cache_get(cache_key)
        if cached:
            logger.debug("Dashboard stats served from cache", user_id=user_id)
            return cached

        # Total resumes
        total_resumes = await self._count(db, Resume, user_id)

        # Total jobs
        total_jobs = await self._count(db, Job, user_id)

        # Total analyses
        total_analyses = await self._count(db, ATSAnalysis, user_id)

        # Total cover letters
        total_cover_letters = await self._count(db, CoverLetter, user_id)

        # Average ATS score
        avg_result = await db.execute(
            select(func.avg(ATSAnalysis.overall_score)).where(
                ATSAnalysis.user_id == user_id
            )
        )
        avg_score = avg_result.scalar()

        # Best ATS score
        best_result = await db.execute(
            select(func.max(ATSAnalysis.overall_score)).where(
                ATSAnalysis.user_id == user_id
            )
        )
        best_score = best_result.scalar()

        # Last upload timestamp
        last_upload_result = await db.execute(
            select(func.max(Resume.created_at)).where(Resume.user_id == user_id)
        )
        last_upload = last_upload_result.scalar()

        stats = {
            "total_resumes": total_resumes,
            "total_analyses": total_analyses,
            "total_jobs": total_jobs,
            "total_cover_letters": total_cover_letters,
            "average_ats_score": round(avg_score, 2) if avg_score else 0.0,
            "best_ats_score": round(best_score, 2) if best_score else 0.0,
            "last_upload": last_upload.isoformat() if last_upload else None,
        }

        await cache_set(cache_key, stats, ttl=settings.CACHE_TTL_SECONDS)
        logger.info("Dashboard stats computed and cached", user_id=user_id)
        return stats

    async def get_analytics(
        self, db: AsyncSession, user_id: str, days: int = 30
    ) -> dict:
        """
        Get analytics data for charts (score trends, component averages).

        Args:
            db: Async database session.
            user_id: User UUID string.
            days: Number of days to look back.

        Returns:
            Dict with score_trend, component_averages, top_matched_jobs.
        """
        cache_key = f"cache:analytics:{user_id}:{days}"
        cached = await cache_get(cache_key)
        if cached:
            logger.debug("Analytics served from cache", user_id=user_id, days=days)
            return cached

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Score trend: daily average scores
        trend_result = await db.execute(
            select(
                func.date(ATSAnalysis.created_at).label("date"),
                func.avg(ATSAnalysis.overall_score).label("avg_score"),
                func.count(ATSAnalysis.id).label("count"),
            )
            .where(
                ATSAnalysis.user_id == user_id,
                ATSAnalysis.created_at >= cutoff,
            )
            .group_by(func.date(ATSAnalysis.created_at))
            .order_by(func.date(ATSAnalysis.created_at))
        )
        trend_rows = trend_result.all()
        score_trend = [
            {
                "date": str(row.date),
                "score": round(float(row.avg_score), 2),
                "count": int(row.count),
            }
            for row in trend_rows
        ]

        # Component averages
        comp_result = await db.execute(
            select(
                func.avg(ATSAnalysis.keyword_score).label("keyword"),
                func.avg(ATSAnalysis.formatting_score).label("formatting"),
                func.avg(ATSAnalysis.section_score).label("section"),
                func.avg(ATSAnalysis.skills_score).label("skills"),
                func.avg(ATSAnalysis.experience_score).label("experience"),
            )
            .where(
                ATSAnalysis.user_id == user_id,
                ATSAnalysis.created_at >= cutoff,
            )
        )
        comp_row = comp_result.first()
        component_averages = {
            "keyword_match": round(float(comp_row.keyword or 0), 2),
            "formatting": round(float(comp_row.formatting or 0), 2),
            "section_completeness": round(float(comp_row.section or 0), 2),
            "skills_match": round(float(comp_row.skills or 0), 2),
            "experience_relevance": round(float(comp_row.experience or 0), 2),
        }

        # Top matched jobs (highest scoring analyses)
        top_result = await db.execute(
            select(ATSAnalysis, Job)
            .join(Job, ATSAnalysis.job_id == Job.id, isouter=True)
            .where(
                ATSAnalysis.user_id == user_id,
                ATSAnalysis.job_id.is_not(None),
            )
            .order_by(ATSAnalysis.overall_score.desc())
            .limit(5)
        )
        top_rows = top_result.all()
        top_matched_jobs = [
            {
                "job_title": row.Job.title if row.Job else "Unknown",
                "company": row.Job.company if row.Job else None,
                "score": round(row.ATSAnalysis.overall_score, 2),
                "analysis_id": str(row.ATSAnalysis.id),
            }
            for row in top_rows
        ]

        analytics = {
            "score_trend": score_trend,
            "component_averages": component_averages,
            "top_matched_jobs": top_matched_jobs,
            "period_days": days,
        }

        await cache_set(cache_key, analytics, ttl=settings.CACHE_TTL_SECONDS)
        logger.info("Analytics computed and cached", user_id=user_id, days=days)
        return analytics

    async def get_activity(self, db: AsyncSession, user_id: str, limit: int = 10) -> dict:
        """
        Get recent user activity feed.

        Combines events from resumes, analyses, cover letters, and interview sessions,
        sorted by timestamp descending.
        """
        activities = []
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # Recent resume uploads
        resume_result = await db.execute(
            select(Resume)
            .where(Resume.user_id == user_id, Resume.created_at >= cutoff)
            .order_by(Resume.created_at.desc())
            .limit(limit)
        )
        for resume in resume_result.scalars():
            activities.append({
                "type": "resume_uploaded",
                "description": f"Uploaded {resume.filename}",
                "timestamp": resume.created_at.isoformat(),
                "metadata": {"resume_id": str(resume.id), "status": resume.status},
            })

        # Recent ATS analyses
        analysis_result = await db.execute(
            select(ATSAnalysis, Job)
            .join(Job, ATSAnalysis.job_id == Job.id, isouter=True)
            .where(ATSAnalysis.user_id == user_id, ATSAnalysis.created_at >= cutoff)
            .order_by(ATSAnalysis.created_at.desc())
            .limit(limit)
        )
        for analysis, job in analysis_result.all():
            job_info = f" for {job.title}" + (f" at {job.company}" if job and job.company else "") if job else ""
            activities.append({
                "type": "ats_analysis_completed",
                "description": f"ATS score: {analysis.overall_score:.0f}{job_info}",
                "timestamp": analysis.created_at.isoformat(),
                "metadata": {
                    "analysis_id": str(analysis.id),
                    "score": analysis.overall_score,
                },
            })

        # Recent cover letters
        letter_result = await db.execute(
            select(CoverLetter)
            .where(CoverLetter.user_id == user_id, CoverLetter.created_at >= cutoff)
            .order_by(CoverLetter.created_at.desc())
            .limit(5)
        )
        for letter in letter_result.scalars():
            activities.append({
                "type": "cover_letter_generated",
                "description": f"Cover letter generated ({letter.tone} tone)",
                "timestamp": letter.created_at.isoformat(),
                "metadata": {"letter_id": str(letter.id)},
            })

        # Sort all activities by timestamp descending
        activities.sort(key=lambda x: x["timestamp"], reverse=True)

        return {"activities": activities[:limit]}

    @staticmethod
    async def _count(db: AsyncSession, model, user_id: str) -> int:
        """Count rows for a given model filtered by user_id."""
        result = await db.execute(
            select(func.count(model.id)).where(model.user_id == user_id)
        )
        return int(result.scalar() or 0)

    async def invalidate_user_cache(self, user_id: str) -> None:
        """Invalidate all dashboard caches for a user."""
        from app.core.redis_client import cache_delete_pattern
        await cache_delete_pattern(f"cache:dashboard:{user_id}")
        await cache_delete_pattern(f"cache:analytics:{user_id}:*")
        logger.info("User analytics cache invalidated", user_id=user_id)


# Module-level singleton
analytics_service = AnalyticsService()
