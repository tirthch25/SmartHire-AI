"""
SmartHire AI — PDF Parser Service

Responsibilities:
- Extract raw text from PDF bytes using pdfplumber
- Detect structural elements (sections, bullet points, headers)
- Upload raw PDF to private Vercel Blob storage
- Validate PDF size and MIME type
"""

import io
import re
from dataclasses import dataclass, field
from typing import BinaryIO, Optional

import pdfplumber
import structlog

from app.core.config import settings
from app.core.blob_client import build_resume_key, upload_file

logger = structlog.get_logger(__name__)


@dataclass
class PDFParseResult:
    """Result of parsing a PDF file."""
    raw_text: str
    page_count: int
    word_count: int
    has_bullet_points: bool
    has_section_headers: bool
    detected_sections: list[str] = field(default_factory=list)
    formatting_metadata: dict = field(default_factory=dict)


class PDFParser:
    """
    Extracts and analyzes text from PDF resume files.

    Validation:
        - Max file size: 10 MB (enforced before calling parse())
        - Must be a valid PDF (pdfplumber will raise on invalid files)

    Usage:
        parser = PDFParser()
        result = parser.parse(pdf_bytes)
        s3_key = parser.upload_to_s3(file_obj, user_id, filename)
    """

    # Common resume section keywords (case-insensitive)
    SECTION_KEYWORDS = [
        "experience", "work experience", "employment", "professional experience",
        "education", "academic background", "qualifications",
        "skills", "technical skills", "core competencies", "areas of expertise",
        "projects", "personal projects", "key projects",
        "certifications", "licenses", "credentials",
        "summary", "objective", "profile", "about me",
        "achievements", "accomplishments",
        "publications", "research",
        "volunteer", "activities", "extracurricular",
        "references",
    ]

    # Patterns for bullet points
    BULLET_PATTERNS = [
        r"^\s*[•·▪▸◆\-\*]\s+",   # common bullet chars
        r"^\s*\d+\.\s+",           # numbered lists
        r"^\s*[a-z]\)\s+",         # letter lists
    ]

    def parse(self, pdf_bytes: bytes) -> PDFParseResult:
        """
        Extract text and structural metadata from PDF bytes.

        Args:
            pdf_bytes: Raw bytes of the PDF file.

        Returns:
            PDFParseResult with text and formatting analysis.

        Raises:
            ValueError: If PDF cannot be parsed (corrupted, encrypted, etc.)
        """
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                pages_text = []
                for page in pdf.pages:
                    text = page.extract_text(x_tolerance=3, y_tolerance=3)
                    if text:
                        pages_text.append(text)

                raw_text = "\n\n".join(pages_text).strip()
                page_count = len(pdf.pages)

        except Exception as e:
            logger.error("PDF parsing failed", error=str(e))
            raise ValueError(f"Failed to parse PDF: {e}") from e

        if not raw_text:
            raise ValueError(
                "No text could be extracted from the PDF. "
                "The file may be image-only or encrypted. "
                "Please provide a text-based PDF."
            )

        word_count = len(raw_text.split())
        has_bullets = self._detect_bullet_points(raw_text)
        detected_sections = self._detect_sections(raw_text)
        has_headers = len(detected_sections) > 0

        formatting_meta = {
            "has_bullet_points": has_bullets,
            "has_section_headers": has_headers,
            "detected_sections": detected_sections,
            "page_count": page_count,
            "word_count": word_count,
            "avg_words_per_page": word_count // max(page_count, 1),
            "is_single_page": page_count == 1,
        }

        logger.info(
            "PDF parsed successfully",
            pages=page_count,
            words=word_count,
            sections=len(detected_sections),
        )

        return PDFParseResult(
            raw_text=raw_text,
            page_count=page_count,
            word_count=word_count,
            has_bullet_points=has_bullets,
            has_section_headers=has_headers,
            detected_sections=detected_sections,
            formatting_metadata=formatting_meta,
        )

    def _detect_bullet_points(self, text: str) -> bool:
        """Check if the text contains bullet point patterns."""
        for pattern in self.BULLET_PATTERNS:
            if re.search(pattern, text, re.MULTILINE):
                return True
        return False

    def _detect_sections(self, text: str) -> list[str]:
        """
        Identify resume sections present in the document.
        Looks for section keywords on their own line (case-insensitive).
        """
        lines = text.split("\n")
        found_sections = []

        for line in lines:
            clean_line = line.strip().lower()
            # Section headers are typically short (< 50 chars) and all-caps or title-cased
            if len(clean_line) > 50:
                continue
            for keyword in self.SECTION_KEYWORDS:
                if keyword in clean_line and clean_line not in found_sections:
                    found_sections.append(keyword)
                    break

        return list(dict.fromkeys(found_sections))  # Preserve order, deduplicate

    @staticmethod
    def validate_file_size(file_size_bytes: int) -> None:
        """
        Raise ValueError if file exceeds the configured max size.

        Args:
            file_size_bytes: File size in bytes.
        """
        if file_size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            actual_mb = file_size_bytes / (1024 * 1024)
            raise ValueError(
                f"File size {actual_mb:.1f} MB exceeds maximum allowed {max_mb:.0f} MB"
            )

    @staticmethod
    def upload_to_s3(
        file_obj: BinaryIO,
        user_id: str,
        filename: str,
    ) -> str:
        """
        Upload a PDF file to private Vercel Blob storage.

        Args:
            file_obj: File-like object (already validated).
            user_id: Owner's user UUID as string (used in S3 key path).
            filename: Original filename.

        Returns:
            S3 object key string.
        """
        s3_key = build_resume_key(user_id, filename)
        upload_file(file_obj, s3_key, content_type="application/pdf")
        logger.info("Resume uploaded to private Blob storage", key=s3_key, user_id=user_id)
        return s3_key


# Module-level singleton
pdf_parser = PDFParser()
