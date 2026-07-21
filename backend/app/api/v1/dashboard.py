"""
SmartHire AI — Dashboard API Router

Endpoints:
    GET    /dashboard/stats       Summary statistics (Redis-cached, 5 min)
    GET    /dashboard/analytics   Score trends + component averages (Redis-cached)
    GET    /dashboard/activity    Recent user activity feed
"""

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services.analytics_service import analytics_service

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get(
    "/stats",
    summary="Get dashboard summary statistics",
    status_code=status.HTTP_200_OK,
)
async def get_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns aggregated summary statistics for the user's dashboard.

    Redis-cached for 5 minutes.

    Response includes:
    - Total resumes, analyses, jobs, cover letters
    - Average and best ATS score
    - Last upload timestamp
    """
    return await analytics_service.get_stats(db, user_id)


@router.get(
    "/analytics",
    summary="Get score trends and chart data",
    status_code=status.HTTP_200_OK,
)
async def get_analytics(
    days: int = Query(30, ge=7, le=365, description="Lookback period in days"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns time-series analytics data for chart rendering.

    Redis-cached per user per `days` value.

    Response includes:
    - `score_trend`: Daily average ATS scores (for line chart)
    - `component_averages`: Mean scores per ATS component (for bar/radar chart)
    - `top_matched_jobs`: Highest scoring job matches
    """
    return await analytics_service.get_analytics(db, user_id, days=days)


@router.get(
    "/activity",
    summary="Get recent user activity feed",
    status_code=status.HTTP_200_OK,
)
async def get_activity(
    limit: int = Query(10, ge=1, le=50, description="Max number of activity items"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns a chronological feed of recent user activity.

    Includes:
    - Resume uploads
    - ATS analyses completed
    - Cover letters generated
    - Interview sessions created
    """
    return await analytics_service.get_activity(db, user_id, limit=limit)
