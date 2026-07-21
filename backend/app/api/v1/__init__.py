"""SmartHire AI — API v1 Router Package"""

from fastapi import APIRouter

from app.api.v1 import ats, auth, cover_letter, dashboard, interview, job, resume

# ── v1 Router ─────────────────────────────────────────────────────────────────
api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_v1_router.include_router(resume.router, prefix="/resume", tags=["Resumes"])
api_v1_router.include_router(ats.router, prefix="/ats", tags=["ATS Analysis"])
api_v1_router.include_router(job.router, prefix="/job", tags=["Jobs"])
api_v1_router.include_router(interview.router, prefix="/interview", tags=["Interview"])
api_v1_router.include_router(cover_letter.router, prefix="/cover-letter", tags=["Cover Letters"])
api_v1_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
