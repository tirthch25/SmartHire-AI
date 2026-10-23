"""Move resume/job vectors into PostgreSQL pgvector.

Revision ID: 002_pgvector_embeddings
Revises: 001_initial
"""

from typing import Sequence, Union

from alembic import op

revision: str = "002_pgvector_embeddings"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
    op.execute("""
        CREATE TABLE vector_embeddings (
            id uuid PRIMARY KEY,
            kind varchar(16) NOT NULL CHECK (kind IN ('resume', 'job')),
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            embedding extensions.vector(384) NOT NULL,
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.create_index("ix_vector_embeddings_user_kind", "vector_embeddings", ["user_id", "kind"])
    op.execute(
        "CREATE INDEX ix_vector_embeddings_embedding_cosine "
        "ON vector_embeddings USING hnsw (embedding extensions.vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE vector_embeddings")
    # Keep the shared extension installed; other Supabase objects may use it.
