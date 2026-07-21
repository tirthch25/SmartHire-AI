"""
SmartHire AI — ATS Analysis ORM Model
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ATSAnalysis(Base):
    __tablename__ = "ats_analyses"
    __table_args__ = {"comment": "ATS scoring results for resume-job pairs"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Score Components ──────────────────────────────────────
    overall_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Weighted overall ATS score (0-100)"
    )
    keyword_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Keyword match score — 30% weight"
    )
    formatting_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Formatting quality score — 15% weight"
    )
    section_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Section completeness score — 15% weight"
    )
    skills_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Skills match score — 20% weight"
    )
    experience_score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Experience relevance score — 20% weight"
    )

    # ── Report ────────────────────────────────────────────────
    detailed_report: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Full report: matched/missing keywords, issues, recommendations",
    )
    report_s3_key: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="S3 key of exported PDF report (null until exported)",
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="analyses"
    )
    resume: Mapped["Resume"] = relationship(  # type: ignore[name-defined]
        "Resume", back_populates="analyses"
    )
    job: Mapped["Job | None"] = relationship(  # type: ignore[name-defined]
        "Job", back_populates="analyses"
    )

    @property
    def computed_overall_score(self) -> float:
        """Recalculate overall score from components (for verification)."""
        return (
            self.keyword_score * 0.30
            + self.formatting_score * 0.15
            + self.section_score * 0.15
            + self.skills_score * 0.20
            + self.experience_score * 0.20
        )

    def __repr__(self) -> str:
        return f"<ATSAnalysis id={self.id} overall={self.overall_score:.1f}>"
