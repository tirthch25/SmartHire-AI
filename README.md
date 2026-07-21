# SmartHire AI

> **AI-powered ATS Resume Analyzer** — score your resume, match jobs, close skill gaps, generate interview questions and cover letters.

[![CI](https://github.com/tirthch25/SmartHire-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/tirthch25/SmartHire-AI/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![Next.js 14](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [ATS Score Components](#ats-score-components)
- [Project Structure](#project-structure)
- [Quick Start (Docker)](#quick-start-docker)
- [Local Development](#local-development)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Running Tests](#running-tests)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## Overview

SmartHire AI analyzes resumes against job descriptions using a 5-component ATS scoring engine, semantic embeddings, and Gemini AI. It helps job seekers understand exactly why their resume may fail ATS filters and provides actionable guidance to improve their chances.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Next.js 14 Frontend (Vercel)                          │
│  ┌──────────┐ ┌──────────┐ ┌─────────────────────┐    │
│  │Dashboard │ │ Resume   │ │ Job Match / Cover   │    │
│  │ /profile │ │ Upload   │ │ Letter / Interview  │    │
│  └──────────┘ └──────────┘ └─────────────────────┘    │
└────────────────────────┬────────────────────────────────┘
                         │ REST API (JWT)
┌────────────────────────▼────────────────────────────────┐
│  FastAPI Backend (Render)                               │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Auth │ Resume │ ATS │ Job │ Interview │ CoverLtr │   │
│  └─────────────┬────────────────────────────────────┘   │
│                │ Celery Tasks (Redis Broker)             │
│  ┌─────────────▼────────────────────────────────────┐   │
│  │ AI Services:                                     │   │
│  │  pdf_parser → resume_parser → ats_scorer         │   │
│  │  embedding_service → job_matcher                 │   │
│  │  skill_gap_analyzer → interview_generator        │   │
│  │  cover_letter_generator → pdf_export_service     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │            │            │           │
    PostgreSQL     Redis        AWS S3      ChromaDB
     (Neon)    (Cache+Queue)  (Files)   (Embeddings)
```

### Request Flow

```
User uploads PDF
     │
     ▼
FastAPI → S3 upload → Resume DB record (status: pending)
     │
     ▼
Celery task dispatched (task_id returned to frontend)
     │
     ├─ pdfplumber: text extraction
     ├─ Gemini: entity parsing (name, skills, exp, edu)
     └─ SentenceTransformers → ChromaDB embedding
     │
     ▼
Resume status: completed
     │
     ▼
ATS Analysis triggered (resume_id + job_id)
     │
     ├─ Keyword Match (30%)
     ├─ Formatting Quality (15%)
     ├─ Section Completeness (15%)
     ├─ Skills Match (20%)
     └─ Experience Relevance (20%)
     │
     ▼
Overall ATS Score → PostgreSQL → Frontend polling
```

---

## Features

| Feature | Description |
|---------|-------------|
| **ATS Scoring** | 5-component scoring engine with detailed breakdowns |
| **Resume Parsing** | AI entity extraction: name, email, skills, experience, education |
| **Job Matching** | Semantic + skills + education multi-dimensional match |
| **Skill Gap Analysis** | Missing skills with Gemini-generated learning resources |
| **Interview Prep** | 4 categories × 3 difficulties, hints, sample answers |
| **Cover Letters** | Tone-customized generation with inline editing + PDF export |
| **Analytics Dashboard** | Score trends, component averages, activity feed |
| **PDF Reports** | Professional ATS score reports via ReportLab |
| **JWT Auth** | 15-min access tokens, 7-day refresh tokens (Redis) |
| **Async Processing** | All AI tasks via Celery + Redis with real-time polling |

---

## Tech Stack

### Backend
- **FastAPI** — Async REST API
- **SQLAlchemy 2.0** — Async ORM with PostgreSQL
- **Alembic** — Database migrations
- **Celery** — Distributed task queue
- **Redis** — Broker, result backend, cache
- **Gemini 2.0 Flash** — Entity extraction, generation
- **SentenceTransformers** — `all-MiniLM-L6-v2` embeddings
- **ChromaDB** — Vector similarity search
- **pdfplumber** — PDF text extraction
- **ReportLab** — PDF report generation
- **boto3** — AWS S3 file storage
- **structlog** — Structured JSON logging

### Frontend
- **Next.js 14** — App Router, TypeScript
- **Tailwind CSS** — Utility-first styling
- **Custom CSS Design System** — Dark theme, Inter font

### Infrastructure
- **Docker + Docker Compose** — Local development
- **GitHub Actions** — CI/CD (test → build → deploy)
- **Vercel** — Frontend hosting
- **Render** — Backend hosting
- **Neon** — PostgreSQL (serverless)

---

## ATS Score Components

| Component | Weight | Description |
|-----------|--------|-------------|
| Keyword Match | 30% | TF-IDF + regex overlap with job keywords |
| Formatting Quality | 15% | Length, bullets, sections, quantified achievements |
| Section Completeness | 15% | Presence of required sections |
| Skills Match | 20% | Direct + fuzzy skills overlap |
| Experience Relevance | 20% | Semantic embedding similarity |

**Scoring scale:** 0–100 · ≥75 = Strong · 50–74 = Moderate · <50 = Low

---

## Project Structure

```
SmartHire-AI/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Route handlers (6 routers)
│   │   ├── core/            # Config, DB, Redis, S3, Security, Rate limiter
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # AI services (10 modules)
│   │   └── workers/         # Celery app + 5 tasks
│   ├── alembic/             # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js pages (7 routes)
│   │   ├── components/      # Shared UI components
│   │   └── lib/             # API client, auth helpers
│   ├── Dockerfile
│   └── package.json
├── tests/
│   └── backend/             # pytest test suites (7 files)
├── docs/                    # Architecture, API, DB, Setup docs
├── .github/workflows/       # CI, deploy-backend, deploy-frontend
├── docker-compose.yml
└── pytest.ini
```

---

## Quick Start (Docker)

### Prerequisites
- Docker Desktop
- AWS account (S3 bucket)
- Google Gemini API key
- PostgreSQL connection string (Neon free tier works)

### 1. Clone and configure

```bash
git clone https://github.com/tirthch25/SmartHire-AI.git
cd SmartHire-AI
cp .env.example .env
# Edit .env with your credentials
```

### 2. Start all services

```bash
docker compose up --build
```

This starts:
| Service | Port | URL |
|---------|------|-----|
| FastAPI API | 8000 | http://localhost:8000 |
| Next.js Frontend | 3000 | http://localhost:3000 |
| Celery Flower | 5555 | http://localhost:5555 |
| PostgreSQL | 5432 | — |
| Redis | 6379 | — |
| ChromaDB | 8001 | — |

### 3. Run migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Open the app

- **App:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Celery Monitor:** http://localhost:5555

---

## Local Development

### Backend

```bash
cd backend

# Create virtualenv
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI (auto-reload)
uvicorn app.main:app --reload --port 8000

# Start Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info \
  --queues=resume,ats,ai,export,default

# Start Celery Flower (monitoring)
celery -A app.workers.celery_app flower --port=5555
```

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Application
APP_ENV=development
SECRET_KEY=your-secret-key-min-32-chars
DEBUG=true

# Database (Neon)
DATABASE_URL=postgresql+asyncpg://user:pass@host/smarthire_db?sslmode=require

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# AWS S3
AWS_ACCESS_KEY_ID=your-key-id
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
AWS_S3_BUCKET_NAME=smarthire-ai

# AI
GEMINI_API_KEY=your-gemini-api-key

# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8001

# CORS
ALLOWED_ORIGINS=http://localhost:3000,https://your-domain.vercel.app
```

---

## API Reference

Full API documentation is available at `/docs` (Swagger UI) and `/redoc` when the server is running.

### Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/login` | Login → JWT tokens |
| `GET`  | `/api/v1/auth/me` | Get current user |
| `POST` | `/api/v1/resume/upload` | Upload PDF (→ Celery) |
| `GET`  | `/api/v1/resume/list` | List resumes |
| `DELETE` | `/api/v1/resume/{id}` | Delete resume |
| `POST` | `/api/v1/ats/analyze` | Trigger ATS analysis (→ Celery) |
| `GET`  | `/api/v1/ats/score/{resume_id}` | Latest ATS score |
| `POST` | `/api/v1/job/create` | Save job description |
| `POST` | `/api/v1/job/match` | Semantic match score |
| `GET`  | `/api/v1/job/skill-gap` | Skill gap analysis |
| `POST` | `/api/v1/interview/generate` | Generate questions (→ Celery) |
| `POST` | `/api/v1/cover-letter/generate` | Generate cover letter (→ Celery) |
| `GET`  | `/api/v1/dashboard/stats` | Dashboard summary |
| `GET`  | `/api/v1/dashboard/analytics` | Score trends + charts |
| `GET`  | `/health` | Service health check |

All authenticated endpoints require `Authorization: Bearer <access_token>`.

---

## Running Tests

```bash
cd SmartHire-AI

# Install test dependencies
pip install -r backend/requirements.txt pytest-asyncio httpx

# Run all tests
pytest

# Run specific test file
pytest tests/backend/test_auth.py -v

# Run with coverage
pytest --cov=backend/app --cov-report=html

# Run only unit tests (no external services needed)
pytest -m "not integration"
```

---

## Deployment

### Backend → Render

1. Create a new **Web Service** on Render
2. Connect your GitHub repository
3. Set build command: `pip install -r backend/requirements.txt`
4. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add all environment variables from `.env.example`
6. Set `RENDER_DEPLOY_HOOK_URL` in GitHub Secrets for auto-deploy

### Frontend → Vercel

1. Import your GitHub repository in Vercel
2. Set **Root Directory** to `frontend`
3. Add `NEXT_PUBLIC_API_URL=https://your-render-app.onrender.com/api/v1`
4. Set `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` in GitHub Secrets

### Database → Neon

1. Create a free Neon project
2. Copy the connection string into `DATABASE_URL`
3. Run `alembic upgrade head` to apply migrations

### GitHub Secrets Required

| Secret | Used by |
|--------|---------|
| `SECRET_KEY` | Backend auth |
| `DATABASE_URL` | Production DB |
| `GEMINI_API_KEY` | AI features |
| `AWS_ACCESS_KEY_ID` | S3 storage |
| `AWS_SECRET_ACCESS_KEY` | S3 storage |
| `RENDER_DEPLOY_HOOK_URL` | Backend deploy |
| `VERCEL_TOKEN` | Frontend deploy |
| `VERCEL_ORG_ID` | Frontend deploy |
| `VERCEL_PROJECT_ID` | Frontend deploy |
| `NEXT_PUBLIC_API_URL` | Frontend build |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
