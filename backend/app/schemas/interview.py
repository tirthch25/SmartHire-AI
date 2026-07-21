"""
SmartHire AI — Interview Session Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Question(BaseModel):
    """A single generated interview question."""
    id: int
    question: str
    category: str  # Technical | Behavioral | Situational | Culture Fit
    difficulty: str  # easy | medium | hard
    hints: Optional[List[str]] = None
    sample_answer: Optional[str] = None


class InterviewSessionCreate(BaseModel):
    """Request body for generating interview questions."""
    resume_id: uuid.UUID
    job_id: uuid.UUID
    focus_areas: List[str] = Field(
        default=[],
        max_length=5,
        description="e.g. ['system design', 'behavioral', 'algorithms']",
    )
    difficulty: str = Field(
        default="medium",
        pattern="^(easy|medium|hard)$",
    )
    question_count: int = Field(default=15, ge=5, le=30)


class InterviewSessionResponse(BaseModel):
    """Full interview session record."""
    id: uuid.UUID
    user_id: uuid.UUID
    resume_id: Optional[uuid.UUID]
    job_id: Optional[uuid.UUID]
    questions: List[Question]
    question_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InterviewSessionSummary(BaseModel):
    """Lightweight session info for list views."""
    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    question_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedSessions(BaseModel):
    items: List[InterviewSessionSummary]
    total: int
    page: int
    page_size: int
