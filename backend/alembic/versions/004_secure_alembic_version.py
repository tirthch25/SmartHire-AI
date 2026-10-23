"""Protect Alembic's migration metadata table from the Supabase Data API.

Revision ID: 004_secure_alembic_version
Revises: 003_enable_rls
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004_secure_alembic_version"
down_revision: Union[str, None] = "003_enable_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY")
