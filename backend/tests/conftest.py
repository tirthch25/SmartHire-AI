"""
Shared pytest fixtures for SmartHire AI backend tests.
"""
import os

# Set test environment before any app imports
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://smarthire:smarthire@localhost:5432/smarthire_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("SECRET_KEY", "ci-secret-key-at-least-32-characters-long-for-testing")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-api-key")
os.environ.setdefault("BLOB_READ_WRITE_TOKEN", "test-blob-token")
