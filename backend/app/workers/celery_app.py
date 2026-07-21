"""
SmartHire AI — Celery Application Instance

Configures Celery with:
- Redis as message broker (DB 1)
- Redis as result backend (DB 2)
- Task serialization: JSON
- Task routing for different queues
- Retry policies
"""

from celery import Celery

from app.core.config import settings

# ── Celery App ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "smarthire",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# ── Configuration ─────────────────────────────────────────────────────────────
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezones
    timezone="UTC",
    enable_utc=True,
    # Task execution limits
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    # Worker settings
    worker_concurrency=settings.CELERY_CONCURRENCY,
    worker_prefetch_multiplier=1,   # Process one task at a time (AI tasks are memory-heavy)
    # Result expiry (keep results for 24 hours)
    result_expires=86400,
    # Retry policy defaults
    task_acks_late=True,            # Acknowledge after task completes (not on receipt)
    task_reject_on_worker_lost=True,
    # Task routing
    task_routes={
        "app.workers.tasks.process_resume_upload": {"queue": "resume"},
        "app.workers.tasks.generate_ats_analysis": {"queue": "ats"},
        "app.workers.tasks.generate_cover_letter_task": {"queue": "ai"},
        "app.workers.tasks.generate_interview_questions_task": {"queue": "ai"},
        "app.workers.tasks.export_pdf_report_task": {"queue": "export"},
    },
    # Task queues
    task_default_queue="default",
    # Beat schedule (if needed for future periodic tasks)
    beat_schedule={},
)

# ── Flower Configuration (monitoring) ────────────────────────────────────────
# Access Flower UI at http://localhost:5555
# Start with: celery -A app.workers.celery_app flower --port=5555
