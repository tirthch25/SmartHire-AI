"""
SmartHire AI — Resume Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResumeUploadResponse(BaseModel):
    """Returned immediately after PDF upload is accepted."""
    resume_id: uuid.UUID
    task_id: str
    status: str
    message: str


class ParsedEducation(BaseModel):
    degree: Optional[str] = None
    field: Optional[str] = None
    institution: Optional[str] = None
    year: Optional[int] = None
    gpa: Optional[str] = None


class ParsedExperience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    description: Optional[str] = None
    achievements: List[str] = []


class ParsedProject(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = []
    url: Optional[str] = None


class ParsedCertification(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    year: Optional[int] = None


class ParsedResumeData(BaseModel):
    """Structured resume data extracted by Gemini."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = []
    education: List[ParsedEducation] = []
    experience: List[ParsedExperience] = []
    projects: List[ParsedProject] = []
    certifications: List[ParsedCertification] = []


class ResumeResponse(BaseModel):
    """Full resume record returned from GET /resume/{id}."""
    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    file_size: int
    status: str
    parsed_data: Optional[ParsedResumeData] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeSummary(BaseModel):
    """Lightweight resume info for list views."""
    id: uuid.UUID
    filename: str
    file_size: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResumes(BaseModel):
    items: List[ResumeSummary]
    total: int
    page: int
    page_size: int


class DownloadUrlResponse(BaseModel):
    download_url: str
    expires_in: int = 3600


class TaskStatusResponse(BaseModel):
    """Generic Celery task status poll response."""
    task_id: str
    state: str  # PENDING | PROGRESS | SUCCESS | FAILURE
    progress: Optional[int] = None
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
