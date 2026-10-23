"""SentenceTransformer embeddings stored and searched in PostgreSQL pgvector."""

from functools import lru_cache
from typing import Optional

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = structlog.get_logger(__name__)
EMBEDDING_DIMENSIONS = 384


@lru_cache(maxsize=1)
def _vector_engine() -> Engine:
    """Share a small synchronous pool for vector operations in API and workers."""
    return create_engine(
        settings.sync_database_url,
        pool_size=2,
        max_overflow=3,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


class EmbeddingService:
    """Encode resume/job text and persist vectors in Supabase PostgreSQL."""

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading SentenceTransformer model", model=settings.SENTENCE_TRANSFORMER_MODEL)
            self._model = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
        return self._model

    def encode(self, text_value: str) -> list[float]:
        truncated = " ".join(text_value.split()[:400])
        return self._get_model().encode(truncated, normalize_embeddings=True).tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        truncated = [" ".join(value.split()[:400]) for value in texts]
        vectors = self._get_model().encode(truncated, normalize_embeddings=True, batch_size=32)
        return [vector.tolist() for vector in vectors]

    @staticmethod
    def _vector_literal(embedding: list[float]) -> str:
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"Expected {EMBEDDING_DIMENSIONS} embedding values")
        return "[" + ",".join(str(float(value)) for value in embedding) + "]"

    def _add(self, kind: str, item_id: str, text_value: str, metadata: Optional[dict], embedding: Optional[list[float]]) -> list[float]:
        vector = embedding if embedding is not None else self.encode(text_value)
        meta = dict(metadata or {})
        owner = meta.get("user_id")
        if not owner:
            # Older jobs may predate user_id being included in vector metadata.
            table = "jobs" if kind == "job" else "resumes"
            with _vector_engine().connect() as connection:
                owner = connection.execute(
                    text(f"SELECT user_id::text FROM {table} WHERE id = CAST(:item_id AS uuid)"),
                    {"item_id": item_id},
                ).scalar_one_or_none()
        with _vector_engine().begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO vector_embeddings (id, kind, user_id, embedding, metadata)
                    VALUES (CAST(:item_id AS uuid), :kind, CAST(:user_id AS uuid),
                            CAST(:embedding AS extensions.vector), CAST(:metadata AS jsonb))
                    ON CONFLICT (id) DO UPDATE SET
                        kind = EXCLUDED.kind,
                        user_id = EXCLUDED.user_id,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        updated_at = now()
                """),
                {"item_id": item_id, "kind": kind, "user_id": owner,
                 "embedding": self._vector_literal(vector),
                 "metadata": __import__("json").dumps(meta)},
            )
        logger.info("Embedding stored in pgvector", kind=kind, item_id=item_id)
        return vector

    def add_resume(self, resume_id: str, text: str, metadata: Optional[dict] = None, embedding: Optional[list[float]] = None) -> list[float]:
        return self._add("resume", resume_id, text, metadata, embedding)

    def add_job(self, job_id: str, text: str, metadata: Optional[dict] = None, embedding: Optional[list[float]] = None) -> list[float]:
        return self._add("job", job_id, text, metadata, embedding)

    def _get(self, kind: str, item_id: str) -> Optional[list[float]]:
        with _vector_engine().connect() as connection:
            result = connection.execute(
                text("SELECT embedding::text FROM vector_embeddings WHERE id = CAST(:item_id AS uuid) AND kind = :kind"),
                {"item_id": item_id, "kind": kind},
            ).scalar_one_or_none()
        if result:
            return [float(part) for part in result.strip("[]").split(",")]

        # Backfill vectors created before the ChromaDB-to-pgvector migration.
        source_table, source_field = ("resumes", "raw_text") if kind == "resume" else ("jobs", "description")
        with _vector_engine().connect() as connection:
            row = connection.execute(
                text(f"SELECT {source_field}, user_id::text FROM {source_table} WHERE id = CAST(:item_id AS uuid)"),
                {"item_id": item_id},
            ).first()
        if not row or not row[0]:
            return None
        return self._add(kind, item_id, row[0], {"user_id": row[1]}, None)

    def delete_resume(self, resume_id: str) -> None:
        self._delete(resume_id)

    def delete_job(self, job_id: str) -> None:
        self._delete(job_id)

    @staticmethod
    def _delete(item_id: str) -> None:
        with _vector_engine().begin() as connection:
            connection.execute(text("DELETE FROM vector_embeddings WHERE id = CAST(:item_id AS uuid)"), {"item_id": item_id})

    def get_resume_embedding(self, resume_id: str) -> Optional[list[float]]:
        return self._get("resume", resume_id)

    def get_job_embedding(self, job_id: str) -> Optional[list[float]]:
        return self._get("job", job_id)

    def find_similar_jobs(self, resume_id: str, n_results: int = 5, user_id: Optional[str] = None) -> list[dict]:
        embedding = self.get_resume_embedding(resume_id)
        if embedding is None:
            return []
        vector = self._vector_literal(embedding)
        with _vector_engine().connect() as connection:
            rows = connection.execute(text("""
                SELECT id::text AS job_id, metadata,
                       embedding <=> CAST(:embedding AS extensions.vector) AS cosine_distance
                FROM vector_embeddings
                WHERE kind = 'job' AND (CAST(:user_id AS uuid) IS NULL OR user_id = CAST(:user_id AS uuid))
                ORDER BY embedding <=> CAST(:embedding AS extensions.vector)
                LIMIT :limit
            """), {"embedding": vector, "user_id": user_id, "limit": max(1, n_results)}).mappings().all()
        return [{
            "job_id": row["job_id"],
            "cosine_distance": float(row["cosine_distance"]),
            "similarity_score": round((1 - float(row["cosine_distance"])) * 100, 2),
            "metadata": row["metadata"] or {},
        } for row in rows]

    @staticmethod
    def compute_similarity(embedding_a: list[float], embedding_b: list[float]) -> float:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        return float(cosine_similarity(np.array(embedding_a).reshape(1, -1), np.array(embedding_b).reshape(1, -1))[0][0])


embedding_service = EmbeddingService()
