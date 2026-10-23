"""Enable row-level security on application tables.

Revision ID: 003_enable_rls
Revises: 002_pgvector_embeddings
"""

from typing import Sequence, Union

from alembic import op

revision: str = "003_enable_rls"
down_revision: Union[str, None] = "002_pgvector_embeddings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = (
    "users",
    "resumes",
    "jobs",
    "ats_analyses",
    "interview_sessions",
    "cover_letters",
    "vector_embeddings",
)


def upgrade() -> None:
    # Supabase exposes public-schema tables through its Data API. The app uses
    # its own JWT auth and server-side database connection, not direct table
    # access from Supabase Auth users, so no client-facing policies are added.
    for table in _TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
