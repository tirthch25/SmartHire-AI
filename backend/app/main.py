"""
SmartHire AI — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, ats, cover_letter, dashboard, interview, job, resume
from app.core.config import settings
from app.core.database import init_db
from app.core.rate_limiter import limiter
from app.core.redis_client import close_redis, init_redis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# ── Structured Logging Setup ─────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    format="%(message)s",
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
)

logger = structlog.get_logger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle: connect services on start, disconnect on stop."""
    logger.info("SmartHire AI starting up", env=settings.APP_ENV)

    # Initialize PostgreSQL
    await init_db()
    logger.info("PostgreSQL connected")

    # Initialize Redis
    await init_redis()
    logger.info("Redis connected")

    yield

    # Shutdown
    await close_redis()
    logger.info("SmartHire AI shut down cleanly")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered ATS Resume Analyzer — resume parsing, ATS scoring, "
        "job description matching, skill gap analysis, interview question generation, "
        "and cover letter generation."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


# ── Exception Handlers ───────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a clean 422 response for Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append(
            {
                "field": " → ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )
    logger.warning("Validation error", path=str(request.url), errors=errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Input validation failed",
            "error_code": "VALIDATION_ERROR",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — return 500 and log."""
    logger.error(
        "Unhandled exception",
        path=str(request.url),
        method=request.method,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


# ── API Routers ───────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Authentication"])
app.include_router(resume.router, prefix=f"{API_PREFIX}/resume", tags=["Resume"])
app.include_router(ats.router, prefix=f"{API_PREFIX}/ats", tags=["ATS Scoring"])
app.include_router(job.router, prefix=f"{API_PREFIX}/job", tags=["Job Matching"])
app.include_router(interview.router, prefix=f"{API_PREFIX}/interview", tags=["Interview"])
app.include_router(
    cover_letter.router, prefix=f"{API_PREFIX}/cover-letter", tags=["Cover Letter"]
)
app.include_router(
    dashboard.router, prefix=f"{API_PREFIX}/dashboard", tags=["Dashboard"]
)


# ── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Service health check")
async def health_check():
    """
    Returns the health status of all connected services.
    Used by Docker health checks, load balancers, and monitoring.
    """
    from app.core.database import get_db_status
    from app.core.redis_client import get_redis_status

    db_ok = await get_db_status()
    redis_ok = await get_redis_status()

    overall = "healthy" if (db_ok and redis_ok) else "degraded"

    return {
        "status": overall,
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "services": {
            "database": "connected" if db_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
        },
    }


@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
    }
