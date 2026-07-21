"""
SmartHire AI — Job ORM Model
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"comment": "Job descriptions saved by users for ATS matching"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Full job description text"
    )
    required_skills: Mapped[list | None] = mapped_column(
        JSONB, nullable=True, comment="Gemini-extracted required skills list"
    )
    parsed_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Full structured job requirements from Gemini"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="jobs"
    )
    analyses: Mapped[list["ATSAnalysis"]] = relationship(  # type: ignore[name-defined]
        "ATSAnalysis", back_populates="job"
    )
    cover_letters: Mapped[list["CoverLetter"]] = relationship(  # type: ignore[name-defined]
        "CoverLetter", back_populates="job"
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(  # type: ignore[name-defined]
        "InterviewSession", back_populates="job"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} title={self.title} company={self.company}>"
