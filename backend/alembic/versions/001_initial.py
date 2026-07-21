"""
SmartHire AI — Initial Database Migration

Creates all tables:
- users
- resumes
- ats_analyses
- jobs
- interview_sessions
- cover_letters

Revision: 001_initial
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
import sqlalchemy.dialects.postgresql as pg

# revision identifiers
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── pgcrypto extension for gen_random_uuid() ──────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── resumes ───────────────────────────────────────────────────────────────
    op.create_table(
        "resumes",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="'pending'"),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_data", pg.JSONB(), nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"])
    op.create_index("ix_resumes_status", "resumes", ["status"])
    op.create_index("ix_resumes_created_at", "resumes", ["created_at"])

    # ── jobs ──────────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required_skills", pg.ARRAY(sa.Text()), nullable=True),
        sa.Column("parsed_data", pg.JSONB(), nullable=True),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_user_id", "jobs", ["user_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    # ── ats_analyses ──────────────────────────────────────────────────────────
    op.create_table(
        "ats_analyses",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("resume_id", pg.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("keyword_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("formatting_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("section_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("skills_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("experience_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("detailed_report", pg.JSONB(), nullable=True),
        sa.Column("report_s3_key", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ats_analyses_resume_id", "ats_analyses", ["resume_id"])
    op.create_index("ix_ats_analyses_user_id", "ats_analyses", ["user_id"])
    op.create_index("ix_ats_analyses_created_at", "ats_analyses", ["created_at"])
    op.create_index("ix_ats_analyses_overall_score", "ats_analyses", ["overall_score"])

    # ── interview_sessions ────────────────────────────────────────────────────
    op.create_table(
        "interview_sessions",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("resume_id", pg.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False, server_default="'medium'"),
        sa.Column("questions", pg.JSONB(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("focus_areas", pg.ARRAY(sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_interview_sessions_user_id", "interview_sessions", ["user_id"])
    op.create_index("ix_interview_sessions_created_at", "interview_sessions", ["created_at"])

    # ── cover_letters ─────────────────────────────────────────────────────────
    op.create_table(
        "cover_letters",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("resume_id", pg.UUID(as_uuid=True), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default="''"),
        sa.Column("tone", sa.String(50), nullable=False, server_default="'professional'"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("s3_key", sa.String(512), nullable=True),
        sa.Column("highlights", pg.ARRAY(sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cover_letters_user_id", "cover_letters", ["user_id"])
    op.create_index("ix_cover_letters_created_at", "cover_letters", ["created_at"])


def downgrade() -> None:
    op.drop_table("cover_letters")
    op.drop_table("interview_sessions")
    op.drop_table("ats_analyses")
    op.drop_table("jobs")
    op.drop_table("resumes")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
