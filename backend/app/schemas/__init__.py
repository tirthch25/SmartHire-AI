"""
SmartHire AI — Pydantic Schemas Package
"""

from app.schemas.analysis import ATSAnalysisCreate, ATSAnalysisResponse, ATSComponentDetail
from app.schemas.cover_letter import (
    CoverLetterCreate,
    CoverLetterResponse,
    CoverLetterUpdate,
)
from app.schemas.interview import InterviewSessionCreate, InterviewSessionResponse, Question
from app.schemas.job import JobCreate, JobResponse, JobMatchResponse, SkillGapResponse
from app.schemas.resume import ResumeResponse, ResumeUploadResponse
from app.schemas.user import (
    Token,
    TokenRefresh,
    UserCreate,
    UserLogin,
    UserResponse,
)

__all__ = [
    # User / Auth
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "Token",
    "TokenRefresh",
    # Resume
    "ResumeUploadResponse",
    "ResumeResponse",
    # Job
    "JobCreate",
    "JobResponse",
    "JobMatchResponse",
    "SkillGapResponse",
    # ATS
    "ATSAnalysisCreate",
    "ATSAnalysisResponse",
    "ATSComponentDetail",
    # Cover Letter
    "CoverLetterCreate",
    "CoverLetterUpdate",
    "CoverLetterResponse",
    # Interview
    "InterviewSessionCreate",
    "InterviewSessionResponse",
    "Question",
]
