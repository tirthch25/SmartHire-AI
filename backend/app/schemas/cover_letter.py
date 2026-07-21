"""
SmartHire AI — Cover Letter Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


VALID_TONES = ("professional", "confident", "enthusiastic", "formal")


class CoverLetterCreate(BaseModel):
    """Request body for generating a cover letter."""
    resume_id: uuid.UUID
    job_id: uuid.UUID
    tone: str = Field(default="professional", pattern="^(professional|confident|enthusiastic|formal)$")
    highlights: List[str] = Field(default=[], max_length=10)
    word_limit: int = Field(default=400, ge=100, le=800)


class CoverLetterUpdate(BaseModel):
    """Request body for editing a cover letter."""
    content: str = Field(min_length=50, max_length=5000)


class CoverLetterResponse(BaseModel):
    """Full cover letter record."""
    id: uuid.UUID
    user_id: uuid.UUID
    resume_id: Optional[uuid.UUID]
    job_id: Optional[uuid.UUID]
    content: str
    tone: str
    word_count: int
    s3_key: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_word_count(cls, obj) -> "CoverLetterResponse":
        data = {
            "id": obj.id,
            "user_id": obj.user_id,
            "resume_id": obj.resume_id,
            "job_id": obj.job_id,
            "content": obj.content,
            "tone": obj.tone,
            "word_count": obj.word_count,
            "s3_key": obj.s3_key,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
        }
        return cls(**data)


class CoverLetterSummary(BaseModel):
    """Lightweight cover letter for list views."""
    id: uuid.UUID
    job_id: Optional[uuid.UUID]
    tone: str
    word_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedCoverLetters(BaseModel):
    items: List[CoverLetterSummary]
    total: int
    page: int
    page_size: int


class CoverLetterExportResponse(BaseModel):
    download_url: str
    expires_in: int = 3600
