"""
SmartHire AI — Database Setup

Configures SQLAlchemy 2.0 async engine, session factory, and base model.
Provides:
- Async engine with connection pool settings
- AsyncSession factory
- Base declarative class for ORM models
- Dependency injection helper (get_db)
- DB health check (get_db_status)
"""

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ── Async Engine ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.DEBUG,          # Log SQL in debug mode
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,            # Reconnect on stale connections
    pool_recycle=3600,             # Recycle connections every hour
    connect_args={"server_settings": {"jit": "off"}},  # Disable JIT for asyncpg compat
)

# ── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,        # Avoid lazy-load issues after commit
    autoflush=True,
    autocommit=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ── Database Initialization ───────────────────────────────────────────────────
async def init_db() -> None:
    """
    Called on application startup.
    Verifies database connectivity and creates tables if in development.
    In production, Alembic handles migrations — tables are NOT auto-created.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        if settings.APP_ENV == "development":
            # Only auto-create tables in dev (Alembic manages production)
            async with engine.begin() as conn:
                from app.models import Base as ModelsBase  # noqa: F401 — import triggers model registration
                await conn.run_sync(ModelsBase.metadata.create_all)
            logger.info("Database tables verified/created (development mode)")
        else:
            logger.info("Database connection verified (production — use alembic for migrations)")

    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        raise


# ── Dependency Injection ──────────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency — yields an async database session per request.

    Usage:
        @router.get("/example")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Health Check ──────────────────────────────────────────────────────────────
async def get_db_status() -> bool:
    """Ping the database. Returns True if reachable, False otherwise."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False
