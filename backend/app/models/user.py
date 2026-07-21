"""
SmartHire AI — User ORM Model
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "Registered user accounts"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Primary key",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique user email address",
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="User's display name",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt hash (12 rounds)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Soft-delete / suspension flag",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    resumes: Mapped[list["Resume"]] = relationship(  # type: ignore[name-defined]
        "Resume", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )
    jobs: Mapped[list["Job"]] = relationship(  # type: ignore[name-defined]
        "Job", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )
    analyses: Mapped[list["ATSAnalysis"]] = relationship(  # type: ignore[name-defined]
        "ATSAnalysis", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )
    cover_letters: Mapped[list["CoverLetter"]] = relationship(  # type: ignore[name-defined]
        "CoverLetter", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(  # type: ignore[name-defined]
        "InterviewSession", back_populates="user", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
