# SmartHire AI — Setup Guide

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Local Development (Docker Compose)](#2-local-development-docker-compose)
3. [Manual Local Setup (Without Docker)](#3-manual-local-setup-without-docker)
4. [Environment Variables Reference](#4-environment-variables-reference)
5. [Vercel Blob Setup](#5-vercel-blob-setup)
6. [Supabase PostgreSQL Setup](#6-supabase-postgresql-setup)
7. [Redis Setup (Local + Cloud)](#7-redis-setup-local--cloud)
8. [Production Deployment](#8-production-deployment)
9. [Verifying the Setup](#9-verifying-the-setup)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Docker Desktop | 24.x | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose | v2.x | Bundled with Docker Desktop |
| Node.js | 20 LTS | [nodejs.org](https://nodejs.org) |
| Python | 3.11 | [python.org](https://python.org) |
| Git | 2.x | [git-scm.com](https://git-scm.com) |

---

## 2. Local Development (Docker Compose)

This is the **recommended** approach — runs all 7 services with a single command.

### Step 1: Clone the Repository
```bash
git clone https://github.com/your-username/SmartHire-AI.git
cd SmartHire-AI
```

### Step 2: Configure Environment Variables
```bash
cp .env.example .env
```

Open `.env` and fill in the required values (see [Section 4](#4-environment-variables-reference)).  
**Minimum required for local dev:**
- `GEMINI_API_KEY` — get from [Google AI Studio](https://aistudio.google.com)
- `BLOB_READ_WRITE_TOKEN` — connect a private Vercel Blob store
- `SECRET_KEY` — run `openssl rand -hex 32` to generate

### Step 3: Start All Services
```bash
docker compose up --build
```

This starts:
| Service | URL | Description |
|---------|-----|-------------|
| `api` | http://localhost:8000 | FastAPI API server |
| `frontend` | http://localhost:3000 | Next.js dev server |
| `postgres` | localhost:5432 | PostgreSQL (local only) |
| `redis` | localhost:6379 | Redis cache + broker |
| `celery_worker` | — | Background task worker |
| `flower` | http://localhost:5555 | Celery monitoring UI |

### Step 4: Run Database Migrations
```bash
docker compose exec api alembic upgrade head
```

### Step 5: Verify
- API docs: http://localhost:8000/api/docs
- Frontend: http://localhost:3000
- Flower UI: http://localhost:5555

---

## 3. Manual Local Setup (Without Docker)

Use this for faster development iteration without rebuilding containers.

### Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Copy env
cp ../.env.example .env
# Fill in your values

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Start Celery Worker (separate terminal)
```bash
cd backend
source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
```

### Start Celery Flower (optional)
```bash
cd backend
source venv/bin/activate
celery -A app.workers.celery_app flower --port=5555
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy env
cp ../.env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1

# Start dev server
npm run dev
```

### Local Services Required
- PostgreSQL 16 running on `localhost:5432`
- Redis 7 running on `localhost:6379`

---

## 4. Environment Variables Reference

Create a `.env` file at the project root. Copy from `.env.example`.

### Backend Variables

```env
# ── Application ──────────────────────────────────────────────
APP_NAME="SmartHire AI"
APP_ENV=development          # development | production
DEBUG=true
LOG_LEVEL=INFO

# ── Security ─────────────────────────────────────────────────
SECRET_KEY=                  # REQUIRED: min 32 chars (openssl rand -hex 32)
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ALLOWED_ORIGINS=http://localhost:3000

# ── Database (PostgreSQL) ─────────────────────────────────────
DATABASE_URL=                # REQUIRED: postgresql+asyncpg://user:pass@host:5432/dbname
# Local example: postgresql+asyncpg://smarthire:smarthire@localhost:5432/smarthire_db

# ── Redis ────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Celery ───────────────────────────────────────────────────
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_CONCURRENCY=4

# ── Vercel Blob ───────────────────────────────────────────────
BLOB_READ_WRITE_TOKEN=       # REQUIRED: private Vercel Blob store token

# ── AI / ML ──────────────────────────────────────────────────
GEMINI_API_KEY=              # REQUIRED: from Google AI Studio
GEMINI_MODEL=gemini-2.0-flash
SENTENCE_TRANSFORMER_MODEL=all-MiniLM-L6-v2


# ── Rate Limiting ────────────────────────────────────────────
RATE_LIMIT_DEFAULT=60/minute
RATE_LIMIT_AUTH=10/minute
RATE_LIMIT_UPLOAD=5/minute
```

### Frontend Variables (`.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_NAME="SmartHire AI"
```

> [!CAUTION]
> Never commit `.env` or `.env.local` to version control. They are listed in `.gitignore`.

---

## 5. Vercel Blob Setup

1. In your Vercel project, open **Storage** and create a Blob store with access set to **Private**.
2. Connect the store to the project and configure Vercel Blob credentials in the API and Celery daemon environments. The official Python SDK uses Vercel OIDC when the store is connected; `BLOB_READ_WRITE_TOKEN` also works for local development and non-Vercel environments.
3. The API checks the user's JWT and ownership before streaming resumes and generated PDFs from private storage.
## 6. Supabase PostgreSQL Setup

1. Create a project at [supabase.com](https://supabase.com)
2. In **Project Settings → Database → Connection string**, select **Session pooler** for the long-lived API and worker connections
3. Copy the URI and adapt it for asyncpg:
   ```
   postgresql+asyncpg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?ssl=require
   ```
4. URL-encode reserved characters in the password and set `DATABASE_URL` in the API, worker, and migration environments.

> [!NOTE]
> Use the Session Pooler URL (port 5432) for this SQLAlchemy/asyncpg application. Keep the database URL out of `NEXT_PUBLIC_*` frontend variables.

---

## 7. Redis Setup (Local + Cloud)

### Local (Docker — already included in docker-compose.yml)
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Production (Upstash — recommended free tier)
1. Go to [upstash.com](https://upstash.com)
2. Create a new Redis database
3. Region: match your Vercel deployment region
4. Copy the `REDIS_URL` (format: `redis://:password@host:port`)
5. Set `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` in Vercel environment variables

---

## 8. Production Deployment

See [deployment.md](deployment.md) for Vercel Services and Daemons, Supabase, environment variables, migrations, and deployment steps.
## 9. Verifying the Setup

Run these checks after setup:

```bash
# 1. Backend health check
curl http://localhost:8000/health
# Expected: `status` is `healthy`; `services.database` and `services.redis` are `connected`.

# 2. API docs accessible
open http://localhost:8000/api/docs

# 3. Register a test user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test1234!","full_name":"Test User"}'

# 4. Run backend tests
cd backend && pytest tests/ -v --tb=short

# 5. Frontend builds without errors
cd frontend && npm run build
```

---

## 10. Troubleshooting

### `Error: connection refused` on DATABASE_URL
- Ensure PostgreSQL is running: `docker compose ps`
- For Supabase: use the Session Pooler URL with `?ssl=require` and check the password is URL-encoded

### Celery tasks stuck in `PENDING`
- Verify Redis is reachable: `redis-cli ping` → `PONG`
- Check `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are set correctly
- Check Celery worker logs: `docker compose logs celery_worker`

### `ModuleNotFoundError: sentence_transformers`
- The first run downloads the `all-MiniLM-L6-v2` model (~90 MB). Ensure internet access.
- Model is cached at `~/.cache/huggingface/` after first download.


### JWT `401 Unauthorized`
- Access tokens expire in 15 minutes — use `POST /auth/refresh` to renew
- Ensure `Authorization: Bearer <token>` header is sent (not `Token` or `JWT`)
