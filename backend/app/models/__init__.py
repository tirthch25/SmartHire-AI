"""
SmartHire AI — SQLAlchemy ORM Models Package

Import all models here so SQLAlchemy's MetaData is fully populated
before Alembic autogenerate and before init_db() creates tables.
"""

from app.core.database import Base  # noqa: F401
from app.models.analysis import ATSAnalysis  # noqa: F401
from app.models.cover_letter import CoverLetter  # noqa: F401
from app.models.interview_session import InterviewSession  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.resume import Resume  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "Base",
    "User",
    "Resume",
    "Job",
    "ATSAnalysis",
    "CoverLetter",
    "InterviewSession",
]
