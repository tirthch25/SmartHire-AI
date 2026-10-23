"""Synchronous Vercel Blob helpers for the FastAPI and Celery services."""

import uuid
from typing import BinaryIO

import structlog
from vercel.blob import sync as blob

logger = structlog.get_logger(__name__)


def build_resume_key(user_id: str, filename: str) -> str:
    """Build a unique Vercel Blob pathname for a resume PDF."""
    unique_id = uuid.uuid4().hex[:8]
    safe_name = filename.replace(" ", "_")
    return f"resumes/{user_id}/{unique_id}_{safe_name}"


def build_report_key(user_id: str, analysis_id: str) -> str:
    return f"reports/{user_id}/{analysis_id}_report.pdf"


def build_cover_letter_key(user_id: str, letter_id: str) -> str:
    return f"cover-letters/{user_id}/{letter_id}_cover_letter.pdf"


def upload_file(file_obj: BinaryIO, blob_pathname: str, content_type: str = "application/pdf") -> str:
    return upload_bytes(file_obj.read(), blob_pathname, content_type)


def upload_bytes(data: bytes, blob_pathname: str, content_type: str = "application/pdf") -> str:
    """Upload a private blob and return its delivery URL."""
    try:
        result = blob.put_blob(
            blob_pathname,
            data,
            access="private",
            content_type=content_type,
            allow_overwrite=True,
        )
        logger.info("Private Vercel Blob uploaded", pathname=result.pathname, size_bytes=len(data))
        return result.url
    except Exception as exc:
        logger.exception("Private Vercel Blob upload failed", pathname=blob_pathname)
        raise RuntimeError(f"Vercel Blob upload failed: {exc}") from exc


def download_bytes(blob_pathname_or_url: str) -> bytes:
    """Download a private blob by pathname or delivery URL."""
    try:
        return blob.get_blob(blob_pathname_or_url, access="private").body
    except Exception as exc:
        logger.exception("Private Vercel Blob download failed", blob=blob_pathname_or_url)
        raise RuntimeError(f"Vercel Blob download failed: {exc}") from exc


def generate_presigned_url(blob_pathname_or_url: str, expiry: int = 3600) -> str:
    """Return the private delivery URL for server-side compatibility only."""
    del expiry  # Private blobs are served through authenticated API routes.
    try:
        return blob.head_blob(blob_pathname_or_url).url
    except Exception as exc:
        logger.exception("Private Vercel Blob metadata lookup failed", blob=blob_pathname_or_url)
        raise RuntimeError(f"Vercel Blob lookup failed: {exc}") from exc


def delete_file(blob_pathname_or_url: str) -> bool:
    """Delete a private blob. Vercel treats deletion of a missing blob as success."""
    try:
        blob.delete_blob(blob_pathname_or_url)
        logger.info("Private Vercel Blob deleted", blob=blob_pathname_or_url)
        return True
    except Exception as exc:
        logger.exception("Private Vercel Blob deletion failed", blob=blob_pathname_or_url)
        raise RuntimeError(f"Vercel Blob deletion failed: {exc}") from exc


def object_exists(blob_pathname_or_url: str) -> bool:
    try:
        blob.head_blob(blob_pathname_or_url)
        return True
    except Exception:
        return False
