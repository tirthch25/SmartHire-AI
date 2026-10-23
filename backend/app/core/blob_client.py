"""
SmartHire AI — Vercel Blob Storage Client

Drop-in replacement for s3_client.py using Vercel Blob instead of
Cloudflare R2 / AWS S3.

All public function signatures are kept identical so callers require only
an import-path change:
    from app.core.blob_client import (
        build_resume_key, build_report_key, build_cover_letter_key,
        upload_file, upload_bytes, download_bytes,
        generate_presigned_url, delete_file, object_exists,
    )

Environment variable required:
    BLOB_READ_WRITE_TOKEN  — from Vercel Dashboard → Storage → Blob → Token

How Vercel Blob works (HTTP-based, no SDK needed):
  • Upload  : PUT https://blob.vercel-storage.com/<pathname>
              Header: Authorization: Bearer <token>
              Header: x-content-type: <mime>
              Body  : raw bytes
  • Download: GET  <url>   (public or use token for private blobs)
  • Delete  : DELETE https://blob.vercel-storage.com/<url>
              Header: Authorization: Bearer <token>

Presigned URLs: Vercel Blob urls are already publicly accessible CDN links.
For private blobs the token acts as the bearer — we return the blob URL directly.
The `expiry` parameter is accepted for API compatibility but has no effect
(Vercel Blob URLs don't expire unless the blob is deleted).

Docs: https://vercel.com/docs/storage/vercel-blob/using-blob-sdk
"""

import io
import uuid
from typing import BinaryIO, Optional

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# Vercel Blob API base URL
_BLOB_API_URL = "https://blob.vercel-storage.com"


def _token() -> str:
    """Return the Vercel Blob read-write token from settings."""
    token = settings.BLOB_READ_WRITE_TOKEN
    if not token:
        raise RuntimeError(
            "BLOB_READ_WRITE_TOKEN is not set. "
            "Get it from Vercel Dashboard → Storage → Blob → Connect & get token."
        )
    return token


# ── Key / Pathname Builders ───────────────────────────────────────────────────

def build_resume_key(user_id: str, filename: str) -> str:
    """
    Build a unique Vercel Blob pathname for a resume PDF.
    Format: resumes/{user_id}/{uuid}_{filename}
    """
    unique_id = uuid.uuid4().hex[:8]
    safe_name = filename.replace(" ", "_")
    return f"resumes/{user_id}/{unique_id}_{safe_name}"


def build_report_key(user_id: str, analysis_id: str) -> str:
    """Build Vercel Blob pathname for an ATS report PDF."""
    return f"reports/{user_id}/{analysis_id}_report.pdf"


def build_cover_letter_key(user_id: str, letter_id: str) -> str:
    """Build Vercel Blob pathname for a cover letter PDF."""
    return f"cover-letters/{user_id}/{letter_id}_cover_letter.pdf"


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_file(
    file_obj: BinaryIO,
    blob_pathname: str,
    content_type: str = "application/pdf",
) -> str:
    """
    Upload a file-like object to Vercel Blob.

    Args:
        file_obj     : File-like object with a .read() method.
        blob_pathname: Target pathname (used as the Blob key).
        content_type : MIME type for the stored object.

    Returns:
        The blob_pathname on success.

    Raises:
        RuntimeError on upload failure.
    """
    data = file_obj.read()
    return upload_bytes(data, blob_pathname, content_type)


def upload_bytes(
    data: bytes,
    blob_pathname: str,
    content_type: str = "application/pdf",
) -> str:
    """
    Upload raw bytes to Vercel Blob.

    Args:
        data         : Raw bytes to upload.
        blob_pathname: Target pathname.
        content_type : MIME type.

    Returns:
        The blob_pathname on success.

    Raises:
        RuntimeError on upload failure.
    """
    url = f"{_BLOB_API_URL}/{blob_pathname}"
    headers = {
        "Authorization": f"Bearer {_token()}",
        "x-content-type": content_type,
        # access: public makes the blob reachable via its CDN URL without a token
        "x-access": "public",
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.put(url, content=data, headers=headers)
            response.raise_for_status()

        blob_url = response.json().get("url", url)
        logger.info(
            "Vercel Blob upload successful",
            pathname=blob_pathname,
            blob_url=blob_url,
            size_bytes=len(data),
        )
        return blob_pathname

    except httpx.HTTPStatusError as e:
        logger.error(
            "Vercel Blob upload failed",
            pathname=blob_pathname,
            status=e.response.status_code,
            body=e.response.text,
        )
        raise RuntimeError(f"Vercel Blob upload failed [{e.response.status_code}]: {e.response.text}") from e
    except Exception as e:
        logger.error("Vercel Blob upload error", pathname=blob_pathname, error=str(e))
        raise RuntimeError(f"Vercel Blob upload error: {e}") from e


# ── Download ──────────────────────────────────────────────────────────────────

def download_bytes(blob_pathname: str) -> bytes:
    """
    Download a Vercel Blob object and return its raw bytes.

    Args:
        blob_pathname: Blob pathname to download.

    Returns:
        Raw bytes of the object.

    Raises:
        RuntimeError if the object is not found or download fails.
    """
    url = f"{_BLOB_API_URL}/{blob_pathname}"
    headers = {"Authorization": f"Bearer {_token()}"}

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

        data = response.content
        logger.info("Vercel Blob download successful", pathname=blob_pathname, size=len(data))
        return data

    except httpx.HTTPStatusError as e:
        logger.error(
            "Vercel Blob download failed",
            pathname=blob_pathname,
            status=e.response.status_code,
        )
        raise RuntimeError(f"Vercel Blob download failed [{e.response.status_code}]") from e
    except Exception as e:
        logger.error("Vercel Blob download error", pathname=blob_pathname, error=str(e))
        raise RuntimeError(f"Vercel Blob download error: {e}") from e


# ── Public / Presigned URLs ───────────────────────────────────────────────────

def generate_presigned_url(
    blob_pathname: str,
    expiry: int = 3600,  # kept for API compatibility — Vercel Blob URLs don't expire
) -> str:
    """
    Return a public CDN URL for a Vercel Blob object.

    Vercel Blob with x-access: public returns a permanent CDN URL.
    The `expiry` parameter is accepted for drop-in compatibility with the old
    S3 presigned URL signature, but has no effect.

    Args:
        blob_pathname: Blob pathname.
        expiry       : Ignored — kept for backwards compatibility.

    Returns:
        CDN URL string.
    """
    # For public blobs: the URL is deterministic
    # Format: https://<store-id>.public.blob.vercel-storage.com/<pathname>
    # We query the blob metadata to get the exact URL.
    url = f"{_BLOB_API_URL}/{blob_pathname}"
    headers = {"Authorization": f"Bearer {_token()}"}

    try:
        with httpx.Client(timeout=15.0) as client:
            # HEAD request to get blob metadata + URL
            response = client.head(url, headers=headers)
            if response.status_code == 200:
                # The blob's public URL comes back in the response
                cdn_url = str(response.url)
                logger.info("Vercel Blob URL fetched", pathname=blob_pathname, url=cdn_url)
                return cdn_url
            # Fallback: construct the URL from the API endpoint
            return url

    except Exception as e:
        logger.warning(
            "Vercel Blob URL fetch failed, returning API URL",
            pathname=blob_pathname,
            error=str(e),
        )
        return url


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_file(blob_pathname: str) -> bool:
    """
    Delete a Vercel Blob object.

    Returns:
        True on success, False if not found.
    """
    url = f"{_BLOB_API_URL}/{blob_pathname}"
    headers = {"Authorization": f"Bearer {_token()}"}

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.delete(url, headers=headers)

        if response.status_code == 404:
            logger.warning("Vercel Blob delete: pathname not found", pathname=blob_pathname)
            return False

        response.raise_for_status()
        logger.info("Vercel Blob object deleted", pathname=blob_pathname)
        return True

    except httpx.HTTPStatusError as e:
        logger.error(
            "Vercel Blob delete failed",
            pathname=blob_pathname,
            status=e.response.status_code,
        )
        raise RuntimeError(f"Vercel Blob delete failed [{e.response.status_code}]") from e
    except Exception as e:
        logger.error("Vercel Blob delete error", pathname=blob_pathname, error=str(e))
        raise RuntimeError(f"Vercel Blob delete error: {e}") from e


# ── Existence Check ───────────────────────────────────────────────────────────

def object_exists(blob_pathname: str) -> bool:
    """Check if a Vercel Blob object exists without downloading it."""
    url = f"{_BLOB_API_URL}/{blob_pathname}"
    headers = {"Authorization": f"Bearer {_token()}"}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.head(url, headers=headers)
        return response.status_code == 200
    except Exception:
        return False
