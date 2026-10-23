"""
SmartHire AI — pytest Configuration & Shared Fixtures

Provides:
- Async test setup (anyio / asyncio mode)
- In-memory SQLite test database (no credentials needed, fully offline)
- Async SQLAlchemy session factory for tests
- HTTP test client (httpx.AsyncClient)
- Pre-built fixtures: test_user, auth_headers, sample_resume, sample_job
"""

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import String, Text, TypeDecorator, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings  # noqa: F401 — keeps config validated at import
from app.core.database import Base, get_db
import app.core.redis_client  # noqa: F401 — imported for fixture patching
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User

# ── Override rate limiter to use in-memory storage ────────────────────────────
# The production limiter uses `storage_uri=settings.REDIS_URL` (Upstash).
# SlowAPIMiddleware reads `request.app.state.limiter` at request time, so
# replacing it here ensures all unit-test requests hit an in-memory counter.
from slowapi import Limiter as _Limiter
from slowapi.util import get_remote_address as _get_remote_address
import app.core.rate_limiter as _rate_limiter_module

_test_limiter = _Limiter(
    key_func=_get_remote_address,
    storage_uri="memory://",
)
app.state.limiter = _test_limiter
_rate_limiter_module.limiter.enabled = False


# ── SQLite type shims — remap PG-specific types so SQLite can run them ─────────
# SQLite does not understand PostgreSQL UUID or JSONB columns.
# We override them globally on the Base.metadata so that when create_all() runs
# against SQLite it emits VARCHAR / TEXT instead of the PG native types.

class _UUIDString(TypeDecorator):
    """Stores UUID as a 36-char VARCHAR string in SQLite."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return uuid.UUID(value)


class _JSONBText(TypeDecorator):
    """Stores JSONB as a plain TEXT (JSON-serialised) string in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return json.loads(value)


def _patch_pg_types_for_sqlite() -> None:
    """
    Walk every mapped column in Base.metadata and replace PG-specific dialect
    types (UUID, JSONB) with SQLite-compatible shims.  Called once before the
    test engine creates tables.
    """
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
                col.type._isnull = False
            elif isinstance(col.type, JSONB):
                col.type = _JSONBText()


_patch_pg_types_for_sqlite()

# ── In-memory SQLite test engine (aiosqlite, fully offline) ────────────────
# StaticPool: every connection call returns the *same* underlying connection so
# create_all() and subsequent test sessions all see the same in-memory DB.
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    """Enable foreign-key enforcement in SQLite (off by default)."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionFactory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
)


# ── Pytest Configuration ──────────────────────────────────────────────────────
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires external services)"
    )


# ── Session-scoped: Create/Drop Tables ───────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Create all tables before the test session and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_redis():
    """
    Inject a fakeredis client into the redis_client module so that all
    auth endpoints (refresh-token storage, rate limits) work offline.
    """
    import fakeredis.aioredis as fake_aioredis
    import app.core.redis_client as redis_module

    fake_server = fake_aioredis.FakeServer()
    fake_client = fake_aioredis.FakeRedis(
        server=fake_server,
        encoding="utf-8",
        decode_responses=True,
    )
    redis_module._redis_client = fake_client
    yield
    await fake_client.aclose()
    redis_module._redis_client = None


# ── Function-scoped: DB Session ───────────────────────────────────────────────
@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a test database session with automatic rollback after each test.
    Rolls back all changes so tests remain isolated.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


# ── HTTP Client ───────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP test client that overrides the real DB session with the test session.
    All requests in a test share the same rolled-back transaction.
    """
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── User Fixtures ─────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def test_user(db: AsyncSession) -> User:
    """Create and persist a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@smarthire.ai",
        full_name="Test User",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    """Return Authorization headers for the test user."""
    token = create_access_token(subject=str(test_user.id))
    return {"Authorization": f"Bearer {token}"}


# ── Resource Fixtures ─────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def sample_resume(db: AsyncSession, test_user: User) -> Resume:
    """Create a completed resume fixture."""
    resume = Resume(
        id=uuid.uuid4(),
        user_id=test_user.id,
        filename="test_resume.pdf",
        s3_key=f"resumes/{test_user.id}/test_resume.pdf",
        file_size=120_000,
        status="completed",
        raw_text="John Doe\njohn@example.com\nSoftware Engineer with 5 years Python experience.",
        parsed_data={
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+1-555-0100",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
            "experience": [
                {
                    "title": "Senior Software Engineer",
                    "company": "Acme Corp",
                    "duration": "2021-2024",
                    "description": "Built microservices with Python and FastAPI",
                }
            ],
            "education": [
                {
                    "degree": "B.Sc. Computer Science",
                    "institution": "State University",
                    "year": "2019",
                }
            ],
            "certifications": [],
            "projects": [],
        },
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)
    return resume


@pytest_asyncio.fixture
async def sample_job(db: AsyncSession, test_user: User) -> Job:
    """Create a job description fixture."""
    job = Job(
        id=uuid.uuid4(),
        user_id=test_user.id,
        title="Senior Python Developer",
        company="TechCorp",
        description=(
            "We are looking for a Senior Python Developer with experience in FastAPI, "
            "PostgreSQL, Docker, AWS, and microservices architecture. "
            "You will design scalable REST APIs and work with cross-functional teams. "
            "Required: Python 5+ years, FastAPI, PostgreSQL, Docker, AWS, Redis. "
            "Nice to have: Kubernetes, Kafka, Machine Learning."
        ),
        required_skills=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Redis"],
        parsed_data={
            "title": "Senior Python Developer",
            "company": "TechCorp",
            "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Redis"],
            "nice_to_have_skills": ["Kubernetes", "Kafka", "Machine Learning"],
            "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
            "seniority_level": "senior",
            "experience_years": 5,
        },
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    return job
