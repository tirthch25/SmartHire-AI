"""
SmartHire AI — Resume ORM Model
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = {"comment": "Uploaded PDF resumes with S3 reference and parsed data"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Original filename"
    )
    s3_key: Mapped[str] = mapped_column(
        String(512), nullable=False, comment="S3 object key for the raw PDF"
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="File size in bytes"
    )
    raw_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Full text extracted from PDF"
    )
    parsed_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="Gemini-extracted structured entities"
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        comment="pending | processing | completed | failed",
    )
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Celery task ID for processing job"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="resumes"
    )
    analyses: Mapped[list["ATSAnalysis"]] = relationship(  # type: ignore[name-defined]
        "ATSAnalysis", back_populates="resume", cascade="all, delete-orphan"
    )
    cover_letters: Mapped[list["CoverLetter"]] = relationship(  # type: ignore[name-defined]
        "CoverLetter", back_populates="resume"
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(  # type: ignore[name-defined]
        "InterviewSession", back_populates="resume"
    )

    def __repr__(self) -> str:
        return f"<Resume id={self.id} filename={self.filename} status={self.status}>"
