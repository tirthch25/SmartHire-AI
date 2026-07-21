"""
SmartHire AI — ATS Analysis Pydantic Schemas
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ATSAnalysisCreate(BaseModel):
    """Request body to trigger ATS analysis."""
    resume_id: uuid.UUID
    job_id: uuid.UUID


class ATSComponentDetail(BaseModel):
    """Details for a single ATS score component."""
    score: float = Field(ge=0, le=100)
    weight: float
    weighted: float
    description: Optional[str] = None


class ATSScoreComponents(BaseModel):
    keyword_match: ATSComponentDetail
    formatting: ATSComponentDetail
    section_completeness: ATSComponentDetail
    skills_match: ATSComponentDetail
    experience_relevance: ATSComponentDetail


class ATSDetailedReport(BaseModel):
    matched_keywords: List[str] = []
    missing_keywords: List[str] = []
    missing_sections: List[str] = []
    formatting_issues: List[str] = []
    formatting_positives: List[str] = []
    skill_match_details: Optional[Dict[str, List[str]]] = None
    experience_analysis: Optional[Dict[str, Any]] = None
    recommendations: List[str] = []
    strengths: List[str] = []


class ATSAnalysisResponse(BaseModel):
    """Full ATS analysis result."""
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: Optional[uuid.UUID]
    user_id: uuid.UUID
    overall_score: float
    components: ATSScoreComponents
    detailed_report: Optional[ATSDetailedReport] = None
    report_s3_key: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ATSAnalysisSummary(BaseModel):
    """Lightweight ATS analysis for list views."""
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: Optional[uuid.UUID]
    overall_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedAnalyses(BaseModel):
    items: List[ATSAnalysisSummary]
    total: int
    page: int
    page_size: int


class ExportUrlResponse(BaseModel):
    download_url: str
    expires_in: int = 3600
