"""Index foreign keys and remove a duplicate users email index.

Revision ID: 005_index_foreign_keys
Revises: 004_secure_alembic_version
"""

from typing import Sequence, Union

from alembic import op

revision: str = "005_index_foreign_keys"
down_revision: Union[str, None] = "004_secure_alembic_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The unique constraint already provides an index for users.email.
    op.drop_index("ix_users_email", table_name="users")

    op.create_index("ix_ats_analyses_job_id", "ats_analyses", ["job_id"])
    op.create_index("ix_cover_letters_job_id", "cover_letters", ["job_id"])
    op.create_index("ix_cover_letters_resume_id", "cover_letters", ["resume_id"])
    op.create_index("ix_interview_sessions_job_id", "interview_sessions", ["job_id"])
    op.create_index("ix_interview_sessions_resume_id", "interview_sessions", ["resume_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_sessions_resume_id", table_name="interview_sessions")
    op.drop_index("ix_interview_sessions_job_id", table_name="interview_sessions")
    op.drop_index("ix_cover_letters_resume_id", table_name="cover_letters")
    op.drop_index("ix_cover_letters_job_id", table_name="cover_letters")
    op.drop_index("ix_ats_analyses_job_id", table_name="ats_analyses")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
