"""
SmartHire AI — AWS S3 Client

Provides a thin wrapper around boto3 for:
- Uploading files (PDF resumes, generated PDFs)
- Generating presigned GET URLs (temporary download links)
- Deleting objects
- Building consistent S3 key paths
"""

import uuid
from typing import BinaryIO, Optional

import boto3
import structlog
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = structlog.get_logger(__name__)


def _get_s3_client():
    """Create and return a boto3 S3 client using configured credentials."""
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


# ── Key Builders ─────────────────────────────────────────────────────────────

def build_resume_key(user_id: str, filename: str) -> str:
    """
    Build a unique S3 object key for a resume PDF.
    Format: resumes/{user_id}/{uuid}_{filename}
    """
    unique_id = uuid.uuid4().hex[:8]
    safe_name = filename.replace(" ", "_")
    return f"{settings.S3_RESUMES_PREFIX}/{user_id}/{unique_id}_{safe_name}"


def build_report_key(user_id: str, analysis_id: str) -> str:
    """Build S3 key for an ATS report PDF."""
    return f"{settings.S3_REPORTS_PREFIX}/{user_id}/{analysis_id}_report.pdf"


def build_cover_letter_key(user_id: str, letter_id: str) -> str:
    """Build S3 key for a cover letter PDF."""
    return f"{settings.S3_COVER_LETTERS_PREFIX}/{user_id}/{letter_id}_cover_letter.pdf"


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_file(
    file_obj: BinaryIO,
    s3_key: str,
    content_type: str = "application/pdf",
) -> str:
    """
    Upload a file-like object to S3.

    Args:
        file_obj: File-like object with a .read() method.
        s3_key: Target S3 object key.
        content_type: MIME type for the stored object.

    Returns:
        The s3_key on success.

    Raises:
        RuntimeError on upload failure.
    """
    try:
        client = _get_s3_client()
        client.upload_fileobj(
            file_obj,
            settings.AWS_S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={
                "ContentType": content_type,
                "ServerSideEncryption": "AES256",
            },
        )
        logger.info("S3 upload successful", key=s3_key, bucket=settings.AWS_S3_BUCKET_NAME)
        return s3_key
    except (BotoCoreError, ClientError) as e:
        logger.error("S3 upload failed", key=s3_key, error=str(e))
        raise RuntimeError(f"S3 upload failed: {e}") from e


def upload_bytes(
    data: bytes,
    s3_key: str,
    content_type: str = "application/pdf",
) -> str:
    """
    Upload raw bytes to S3.

    Args:
        data: Raw bytes to upload.
        s3_key: Target S3 object key.
        content_type: MIME type.

    Returns:
        The s3_key on success.
    """
    import io
    return upload_file(io.BytesIO(data), s3_key, content_type)


# ── Download ──────────────────────────────────────────────────────────────────

def download_bytes(s3_key: str) -> bytes:
    """
    Download an S3 object and return its raw bytes.

    Args:
        s3_key: S3 object key to download.

    Returns:
        Raw bytes of the object.

    Raises:
        RuntimeError if the object is not found or download fails.
    """
    try:
        client = _get_s3_client()
        response = client.get_object(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=s3_key,
        )
        data = response["Body"].read()
        logger.info("S3 download successful", key=s3_key, size=len(data))
        return data
    except (BotoCoreError, ClientError) as e:
        logger.error("S3 download failed", key=s3_key, error=str(e))
        raise RuntimeError(f"S3 download failed: {e}") from e


# ── Presigned URLs ────────────────────────────────────────────────────────────

def generate_presigned_url(
    s3_key: str,
    expiry: int = settings.S3_PRESIGNED_URL_EXPIRY,
) -> str:
    """
    Generate a presigned GET URL for temporary file access.

    Args:
        s3_key: S3 object key.
        expiry: URL validity in seconds (default: 3600 = 1 hour).

    Returns:
        Presigned HTTPS URL string.

    Raises:
        RuntimeError on failure.
    """
    try:
        client = _get_s3_client()
        url = client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET_NAME, "Key": s3_key},
            ExpiresIn=expiry,
        )
        logger.info("Presigned URL generated", key=s3_key, expiry_seconds=expiry)
        return url
    except (BotoCoreError, ClientError) as e:
        logger.error("Presigned URL generation failed", key=s3_key, error=str(e))
        raise RuntimeError(f"Presigned URL generation failed: {e}") from e


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_file(s3_key: str) -> bool:
    """
    Delete an S3 object.

    Returns:
        True on success, False if the key was not found.
    """
    try:
        client = _get_s3_client()
        client.delete_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key=s3_key)
        logger.info("S3 object deleted", key=s3_key)
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            logger.warning("S3 delete: key not found", key=s3_key)
            return False
        logger.error("S3 delete failed", key=s3_key, error=str(e))
        raise RuntimeError(f"S3 delete failed: {e}") from e
    except BotoCoreError as e:
        logger.error("S3 delete failed", key=s3_key, error=str(e))
        raise RuntimeError(f"S3 delete failed: {e}") from e


# ── Existence Check ───────────────────────────────────────────────────────────

def object_exists(s3_key: str) -> bool:
    """Check if an S3 object exists without downloading it."""
    try:
        client = _get_s3_client()
        client.head_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key=s3_key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise
