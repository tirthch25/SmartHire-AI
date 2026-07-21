"""
SmartHire AI — pytest Configuration & Shared Fixtures

Provides:
- Async test setup (anyio / asyncio mode)
- Test PostgreSQL database (uses a separate test DB)
- Async SQLAlchemy session factory for tests
- HTTP test client (httpx.AsyncClient)
- Pre-built fixtures: test_user, auth_headers, sample_resume, sample_job
"""

import asyncio
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.redis_client import init_redis, close_redis
from app.core.security import hash_password, create_access_token
from app.main import app
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User

# ── Test Database ─────────────────────────────────────────────────────────────
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "/smarthire_db", "/smarthire_test"
).replace("postgresql://", "postgresql+asyncpg://")

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_size=5,
    pool_pre_ping=True,
)

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
    """Initialize Redis for the test session."""
    try:
        await init_redis()
    except Exception:
        pass  # Redis may not be available in all CI environments
    yield
    try:
        await close_redis()
    except Exception:
        pass


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
