"""
SmartHire AI — Cover Letter ORM Model
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

VALID_TONES = ("professional", "confident", "enthusiastic", "formal")


class CoverLetter(Base):
    __tablename__ = "cover_letters"
    __table_args__ = {"comment": "AI-generated cover letters"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Generated cover letter text"
    )
    tone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="professional",
        comment="professional | confident | enthusiastic | formal",
    )
    s3_key: Mapped[str | None] = mapped_column(
        String(512), nullable=True, comment="S3 key of exported PDF (null until exported)"
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="cover_letters"
    )
    resume: Mapped["Resume | None"] = relationship(  # type: ignore[name-defined]
        "Resume", back_populates="cover_letters"
    )
    job: Mapped["Job | None"] = relationship(  # type: ignore[name-defined]
        "Job", back_populates="cover_letters"
    )

    @property
    def word_count(self) -> int:
        """Count words in the cover letter content."""
        return len(self.content.split()) if self.content else 0

    def __repr__(self) -> str:
        return f"<CoverLetter id={self.id} tone={self.tone} words={self.word_count}>"
