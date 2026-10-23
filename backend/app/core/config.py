"""
SmartHire AI — Application Configuration

All settings are loaded from environment variables via Pydantic BaseSettings.
Provides strong typing, validation, and defaults for all configuration values.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings — loaded from .env file or environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────
    APP_NAME: str = "SmartHire AI"
    APP_ENV: str = Field(default="development", pattern="^(development|production|testing)$")
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Security ──────────────────────────────────────────────
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://smarthire:smarthire@localhost:5432/smarthire_db"
    )
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5

    @property
    def async_database_url(self) -> str:
        """Ensure URL uses asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        # Supabase publishes libpq-style sslmode=require URLs; asyncpg expects ssl=require.
        url = url.replace("sslmode=require", "ssl=require")
        return url

    @property
    def sync_database_url(self) -> str:
        """Return the PostgreSQL URL for synchronous SQLAlchemy/psycopg2 clients."""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url.replace("ssl=require", "sslmode=require")

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300  # 5 minutes default cache TTL

    # ── Celery ────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_CONCURRENCY: int = 4
    CELERY_TASK_SOFT_TIME_LIMIT: int = 120  # seconds
    CELERY_TASK_TIME_LIMIT: int = 180       # hard limit

    # ── Vercel Blob File Storage ──────────────────────────────
    # Get from: Vercel Dashboard → Storage → Blob → your store → Connect → Token
    # Format:   vercel_blob_rw_xxxxxxxxxxxxxxxxx
    BLOB_READ_WRITE_TOKEN: str = ""

    # Blob folder path prefixes (used by blob_client key builders)
    BLOB_RESUMES_PREFIX: str = "resumes"
    BLOB_REPORTS_PREFIX: str = "reports"
    BLOB_COVER_LETTERS_PREFIX: str = "cover-letters"

    # URL expiry in seconds (Vercel Blob URLs don't expire, kept for API compat)
    BLOB_PRESIGNED_URL_EXPIRY: int = 3600

    # ── AI / ML ───────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    SENTENCE_TRANSFORMER_MODEL: str = "all-MiniLM-L6-v2"

    # ── File Upload ───────────────────────────────────────────
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_CONTENT_TYPES: List[str] = ["application/pdf"]

    # ── Rate Limiting ─────────────────────────────────────────
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_UPLOAD: str = "5/minute"

    # ── Pagination ────────────────────────────────────────────
    DEFAULT_PAGE_SIZE: int = 10
    MAX_PAGE_SIZE: int = 50


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance (loaded once at startup)."""
    return Settings()


# Module-level singleton — import this directly
settings: Settings = get_settings()
