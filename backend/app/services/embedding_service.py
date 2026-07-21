"""
SmartHire AI — Embedding Service (SentenceTransformers + ChromaDB)

Responsibilities:
- Load and cache the SentenceTransformers model (all-MiniLM-L6-v2)
- Encode text into 384-dimensional embedding vectors
- Manage ChromaDB collections for resumes and jobs
- Store, retrieve, and perform cosine similarity search
"""

import uuid
from typing import Optional

import chromadb
import structlog
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ChromaDB collection names
RESUME_COLLECTION = "smarthire_resumes"
JOB_COLLECTION = "smarthire_jobs"


class EmbeddingService:
    """
    SentenceTransformers + ChromaDB vector store service.

    The model is loaded lazily on first use to avoid slowing startup.
    ChromaDB client connects to the standalone Docker service.

    Usage:
        svc = EmbeddingService()
        embedding = svc.encode("Python developer with 5 years experience")
        svc.add_resume(resume_id="uuid", text="...", metadata={...})
        results = svc.search_similar_jobs(resume_id="uuid", n_results=5)
    """

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._chroma_client: Optional[chromadb.HttpClient] = None
        self._resume_collection = None
        self._job_collection = None

    def _get_model(self) -> SentenceTransformer:
        """Lazy-load the SentenceTransformer model (downloaded on first call)."""
        if self._model is None:
            logger.info(
                "Loading SentenceTransformer model",
                model=settings.SENTENCE_TRANSFORMER_MODEL,
            )
            self._model = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
            logger.info("SentenceTransformer model loaded")
        return self._model

    def _get_chroma_client(self) -> chromadb.HttpClient:
        """Lazy-connect to ChromaDB HTTP server."""
        if self._chroma_client is None:
            self._chroma_client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
            logger.info(
                "ChromaDB client connected",
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
            )
        return self._chroma_client

    def _get_resume_collection(self):
        """Get or create the resumes ChromaDB collection."""
        if self._resume_collection is None:
            client = self._get_chroma_client()
            self._resume_collection = client.get_or_create_collection(
                name=RESUME_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        return self._resume_collection

    def _get_job_collection(self):
        """Get or create the jobs ChromaDB collection."""
        if self._job_collection is None:
            client = self._get_chroma_client()
            self._job_collection = client.get_or_create_collection(
                name=JOB_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
        return self._job_collection

    # ── Encoding ──────────────────────────────────────────────────────────────

    def encode(self, text: str) -> list[float]:
        """
        Encode text into a 384-dimensional vector using SentenceTransformers.

        Args:
            text: Input text (resume or job description).

        Returns:
            List of 384 floats (normalized embedding vector).
        """
        model = self._get_model()
        # Truncate to 512 tokens to avoid SBERT truncation warning
        truncated = " ".join(text.split()[:400])
        embedding = model.encode(truncated, normalize_embeddings=True)
        return embedding.tolist()

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts in a single batch (more efficient)."""
        model = self._get_model()
        truncated = [" ".join(t.split()[:400]) for t in texts]
        embeddings = model.encode(truncated, normalize_embeddings=True, batch_size=32)
        return [e.tolist() for e in embeddings]

    # ── Resume Collection ─────────────────────────────────────────────────────

    def add_resume(
        self,
        resume_id: str,
        text: str,
        metadata: Optional[dict] = None,
        embedding: Optional[list[float]] = None,
    ) -> list[float]:
        """
        Add a resume to ChromaDB.

        Args:
            resume_id: UUID of the resume (used as ChromaDB document ID).
            text: Full resume text.
            metadata: Additional metadata (user_id, created_at, etc.)
            embedding: Pre-computed embedding (if None, will encode text).

        Returns:
            The embedding vector.
        """
        if embedding is None:
            embedding = self.encode(text)

        collection = self._get_resume_collection()
        meta = metadata or {}
        meta["resume_id"] = resume_id

        collection.upsert(
            ids=[resume_id],
            embeddings=[embedding],
            documents=[text[:1000]],  # Store truncated text for reference
            metadatas=[meta],
        )

        logger.info("Resume added to ChromaDB", resume_id=resume_id)
        return embedding

    def delete_resume(self, resume_id: str) -> None:
        """Remove a resume from ChromaDB."""
        collection = self._get_resume_collection()
        collection.delete(ids=[resume_id])
        logger.info("Resume deleted from ChromaDB", resume_id=resume_id)

    def get_resume_embedding(self, resume_id: str) -> Optional[list[float]]:
        """Retrieve stored embedding for a resume."""
        collection = self._get_resume_collection()
        result = collection.get(ids=[resume_id], include=["embeddings"])
        if result["embeddings"]:
            return result["embeddings"][0]
        return None

    # ── Job Collection ────────────────────────────────────────────────────────

    def add_job(
        self,
        job_id: str,
        text: str,
        metadata: Optional[dict] = None,
        embedding: Optional[list[float]] = None,
    ) -> list[float]:
        """
        Add a job description to ChromaDB.

        Args:
            job_id: UUID of the job.
            text: Full job description text.
            metadata: Additional metadata.
            embedding: Pre-computed embedding.

        Returns:
            The embedding vector.
        """
        if embedding is None:
            embedding = self.encode(text)

        collection = self._get_job_collection()
        meta = metadata or {}
        meta["job_id"] = job_id

        collection.upsert(
            ids=[job_id],
            embeddings=[embedding],
            documents=[text[:1000]],
            metadatas=[meta],
        )

        logger.info("Job added to ChromaDB", job_id=job_id)
        return embedding

    def delete_job(self, job_id: str) -> None:
        """Remove a job from ChromaDB."""
        collection = self._get_job_collection()
        collection.delete(ids=[job_id])

    def get_job_embedding(self, job_id: str) -> Optional[list[float]]:
        """Retrieve stored embedding for a job."""
        collection = self._get_job_collection()
        result = collection.get(ids=[job_id], include=["embeddings"])
        if result["embeddings"]:
            return result["embeddings"][0]
        return None

    # ── Similarity Search ─────────────────────────────────────────────────────

    def find_similar_jobs(
        self,
        resume_id: str,
        n_results: int = 5,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Find the most similar jobs for a given resume using cosine similarity.

        Args:
            resume_id: UUID of the resume.
            n_results: Number of results to return.
            user_id: Optional filter to only search within user's jobs.

        Returns:
            List of dicts with job_id, distance, and metadata.
        """
        resume_embedding = self.get_resume_embedding(resume_id)
        if not resume_embedding:
            logger.warning("No embedding found for resume", resume_id=resume_id)
            return []

        collection = self._get_job_collection()
        where = {"user_id": user_id} if user_id else None

        results = collection.query(
            query_embeddings=[resume_embedding],
            n_results=min(n_results, collection.count() or 1),
            where=where,
            include=["distances", "metadatas"],
        )

        output = []
        for i, job_id in enumerate(results["ids"][0]):
            output.append({
                "job_id": job_id,
                "cosine_distance": results["distances"][0][i],
                "similarity_score": round((1 - results["distances"][0][i]) * 100, 2),
                "metadata": results["metadatas"][0][i],
            })

        return output

    def compute_similarity(
        self,
        embedding_a: list[float],
        embedding_b: list[float],
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Returns:
            Similarity score between 0 and 1.
        """
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity

        a = np.array(embedding_a).reshape(1, -1)
        b = np.array(embedding_b).reshape(1, -1)
        return float(cosine_similarity(a, b)[0][0])


# Module-level singleton
embedding_service = EmbeddingService()
