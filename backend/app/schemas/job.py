"""
SmartHire AI — Job Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    """Request body for creating a job description."""
    title: str = Field(min_length=1, max_length=255, strip_whitespace=True)
    company: Optional[str] = Field(None, max_length=255)
    description: str = Field(min_length=50, max_length=50000)


class JobResponse(BaseModel):
    """Full job record returned from API."""
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    company: Optional[str]
    description: str
    required_skills: Optional[List[str]] = []
    parsed_data: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobSummary(BaseModel):
    """Lightweight job info for list views."""
    id: uuid.UUID
    title: str
    company: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedJobs(BaseModel):
    items: List[JobSummary]
    total: int
    page: int
    page_size: int


class JobMatchResponse(BaseModel):
    """Semantic similarity match score between a resume and job."""
    resume_id: uuid.UUID
    job_id: uuid.UUID
    overall_match_score: float = Field(ge=0, le=100)
    skills_overlap: float = Field(ge=0, le=1)
    experience_similarity: float = Field(ge=0, le=1)
    education_match: bool
    matched_skills: List[str]
    missing_skills: List[str]
    bonus_skills: List[str]


class MissingSkillDetail(BaseModel):
    skill: str
    importance: str  # high | medium | low
    learning_resources: List[Dict[str, str]] = []


class SkillGapResponse(BaseModel):
    """Detailed skill gap analysis between resume and job."""
    resume_id: uuid.UUID
    job_id: uuid.UUID
    matched_skills: List[str]
    missing_skills: List[MissingSkillDetail]
    bonus_skills: List[str]
    gap_score: float = Field(ge=0, le=100, description="0 = no gap, 100 = all skills missing")
    recommendations: List[str]
