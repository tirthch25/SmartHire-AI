"""
Alembic environment configuration for SmartHire AI.

Supports async SQLAlchemy (asyncpg) via run_async_migrations().
Reads DATABASE_URL directly from the environment variable — does NOT
import the full application stack, so it works with the minimal deps
installed by the CI/deploy workflow (sqlalchemy, asyncpg, alembic).
"""

import asyncio
import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Standalone Base — imported here so models can register their metadata
# without pulling in the full app.core.database module (which requires
# structlog, pydantic-settings, etc.).
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass

# Import all models so their tables are registered on Base.metadata.
# Each model file imports Base from THIS module via a lazy path, or we
# replicate the metadata registration here by importing the model classes.
# We use a try/except so the deploy job (minimal deps) still works if any
# model's heavy transitive dep is missing — Alembic still runs the
# already-generated migration scripts regardless.
import sys
_here = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_here, ".."))

try:
    # Import model files directly; they define __tablename__ etc.
    # We override their Base reference after the fact.
    from app.models.user import User  # noqa: F401
    from app.models.resume import Resume  # noqa: F401
    from app.models.job import Job  # noqa: F401
    from app.models.analysis import ATSAnalysis  # noqa: F401
    from app.models.cover_letter import CoverLetter  # noqa: F401
    from app.models.interview_session import InterviewSession  # noqa: F401
    # Re-use the Base from app.core.database (it has the full metadata)
    from app.core.database import Base as AppBase  # noqa: F401
    target_metadata = AppBase.metadata
except Exception as _import_err:
    # Minimal-dep environment (CI deploy job) — use our standalone Base.
    # Alembic will still run the migration scripts; autogenerate is not needed
    # during deploy.
    import warnings
    warnings.warn(
        f"Could not import app models ({_import_err}). "
        "Running Alembic with empty metadata — existing migration scripts will still execute.",
        stacklevel=1,
    )
    target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Read DATABASE_URL — prefer environment variable, fall back to alembic.ini
# ---------------------------------------------------------------------------
def _get_db_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    # Normalise driver: postgres:// → postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # Supabase publishes sslmode=require; asyncpg uses ssl=require
    url = url.replace("sslmode=require", "ssl=require")
    return url


# ---------------------------------------------------------------------------
# Alembic wiring
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url — % must be escaped for ConfigParser
config.set_main_option("sqlalchemy.url", _get_db_url().replace("%", "%%"))


def run_migrations_offline() -> None:
    """Offline mode — emit SQL script without a live connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Online mode — connect to the DB and run migrations."""
    connectable = create_async_engine(_get_db_url())
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
