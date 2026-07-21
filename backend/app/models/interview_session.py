"""
SmartHire AI — Interview Session ORM Model
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    __table_args__ = {"comment": "AI-generated interview question sessions"}

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
    questions: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Array of {id, question, category, difficulty, hints, sample_answer}",
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="interview_sessions"
    )
    resume: Mapped["Resume | None"] = relationship(  # type: ignore[name-defined]
        "Resume", back_populates="interview_sessions"
    )
    job: Mapped["Job | None"] = relationship(  # type: ignore[name-defined]
        "Job", back_populates="interview_sessions"
    )

    @property
    def question_count(self) -> int:
        return len(self.questions) if self.questions else 0

    def __repr__(self) -> str:
        return f"<InterviewSession id={self.id} questions={self.question_count}>"
