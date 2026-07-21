# SmartHire AI — Setup Guide

## Table of Contents
1. [Prerequisites](#1-prerequisites)
2. [Local Development (Docker Compose)](#2-local-development-docker-compose)
3. [Manual Local Setup (Without Docker)](#3-manual-local-setup-without-docker)
4. [Environment Variables Reference](#4-environment-variables-reference)
5. [AWS S3 Setup](#5-aws-s3-setup)
6. [Neon PostgreSQL Setup](#6-neon-postgresql-setup)
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
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME` — see [Section 5](#5-aws-s3-setup)
- `SECRET_KEY` — run `openssl rand -hex 32` to generate

### Step 3: Start All Services
```bash
docker compose up --build
```

This starts:
| Service | URL | Description |
|---------|-----|-------------|
| `backend` | http://localhost:8000 | FastAPI API server |
| `frontend` | http://localhost:3000 | Next.js dev server |
| `chromadb` | http://localhost:8001 | ChromaDB vector DB |
| `postgres` | localhost:5432 | PostgreSQL (local only) |
| `redis` | localhost:6379 | Redis cache + broker |
| `celery-worker` | — | Background task worker |
| `celery-flower` | http://localhost:5555 | Celery monitoring UI |

### Step 4: Run Database Migrations
```bash
docker compose exec backend alembic upgrade head
```

### Step 5: Verify
- API docs: http://localhost:8000/docs
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
- ChromaDB running on `localhost:8001` (or use Docker: `docker run -p 8001:8000 chromadb/chroma`)

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

# ── AWS S3 ───────────────────────────────────────────────────
AWS_ACCESS_KEY_ID=           # REQUIRED
AWS_SECRET_ACCESS_KEY=       # REQUIRED
AWS_REGION=us-east-1
AWS_S3_BUCKET_NAME=          # REQUIRED: e.g. smarthire-ai-prod

# ── AI / ML ──────────────────────────────────────────────────
GEMINI_API_KEY=              # REQUIRED: from Google AI Studio
GEMINI_MODEL=gemini-2.0-flash
SENTENCE_TRANSFORMER_MODEL=all-MiniLM-L6-v2

# ── ChromaDB ─────────────────────────────────────────────────
CHROMA_HOST=localhost
CHROMA_PORT=8001

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

## 5. AWS S3 Setup

### Step 1: Create an S3 Bucket

1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com)
2. Click **Create bucket**
3. Name: `smarthire-ai-prod` (must be globally unique)
4. Region: `us-east-1` (or your preferred region)
5. **Block all public access**: ✅ Enabled (files served via presigned URLs only)
6. Versioning: Optional (recommended for production)
7. Click **Create bucket**

### Step 2: Create Folder Structure
Create these prefixes (folders) in the bucket:
- `resumes/`
- `reports/`
- `cover-letters/`

### Step 3: Create IAM User + Policy

1. Go to **IAM → Users → Create user**
2. Name: `smarthire-ai-api`
3. Attach policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SmartHireS3Access",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:GeneratePresignedUrl"
      ],
      "Resource": "arn:aws:s3:::smarthire-ai-prod/*"
    }
  ]
}
```

4. Go to **Security credentials → Create access key**
5. Copy `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` into your `.env`

### Step 4: Configure CORS on the Bucket

In S3 → Bucket → Permissions → CORS configuration:
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST"],
    "AllowedOrigins": ["https://your-frontend-domain.vercel.app"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

---

## 6. Neon PostgreSQL Setup

1. Go to [neon.tech](https://neon.tech) and create a free account
2. Create a new **Project** named `smarthire-ai`
3. Create a **Database** named `smarthire_db`
4. In **Connection Details**, select the **Pooler** connection string for production
5. Copy the connection string:
   ```
   postgresql+asyncpg://user:password@ep-xxx.us-east-1.aws.neon.tech/smarthire_db?sslmode=require
   ```
6. Set `DATABASE_URL` in your environment

> [!NOTE]
> Neon's free tier provides 0.5 GB storage and auto-suspends after 5 minutes of inactivity — sufficient for development and small production workloads.

---

## 7. Redis Setup (Local + Cloud)

### Local (Docker — already included in docker-compose.yml)
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Production (Upstash — recommended free tier)
1. Go to [upstash.com](https://upstash.com)
2. Create a new Redis database
3. Region: match your Render backend region
4. Copy the `REDIS_URL` (format: `redis://:password@host:port`)
5. Set `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` in Render env vars

---

## 8. Production Deployment

### Backend → Render

1. Go to [render.com](https://render.com) → New → **Web Service**
2. Connect your GitHub repository
3. Settings:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from Section 4
5. Create a second **Background Worker** service for Celery:
   - **Root Directory**: `backend`
   - **Start Command**: `celery -A app.workers.celery_app worker --loglevel=info`

### Database Migrations (Render)
Add a **Job** on Render that runs on each deploy:
```bash
alembic upgrade head
```

### Frontend → Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# From project root
cd frontend
vercel --prod
```

Or connect via Vercel GitHub integration:
1. Go to [vercel.com](https://vercel.com) → New Project
2. Import your GitHub repository
3. **Root Directory**: `frontend`
4. Add environment variable: `NEXT_PUBLIC_API_URL=https://your-render-api.onrender.com/api/v1`

---

## 9. Verifying the Setup

Run these checks after setup:

```bash
# 1. Backend health check
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected","redis":"connected","chromadb":"connected"}

# 2. API docs accessible
open http://localhost:8000/docs

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
- For Neon: check `?sslmode=require` is in the URL

### Celery tasks stuck in `PENDING`
- Verify Redis is reachable: `redis-cli ping` → `PONG`
- Check `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are set correctly
- Check Celery worker logs: `docker compose logs celery-worker`

### `ModuleNotFoundError: sentence_transformers`
- The first run downloads the `all-MiniLM-L6-v2` model (~90 MB). Ensure internet access.
- Model is cached at `~/.cache/huggingface/` after first download.

### S3 `Access Denied`
- Verify IAM policy has `s3:PutObject` and `s3:GetObject` on the correct bucket ARN
- Check `AWS_REGION` matches the bucket's region

### ChromaDB connection issues
- Ensure ChromaDB is running: `docker compose ps chromadb`
- Default host: `localhost`, port: `8001`

### JWT `401 Unauthorized`
- Access tokens expire in 15 minutes — use `POST /auth/refresh` to renew
- Ensure `Authorization: Bearer <token>` header is sent (not `Token` or `JWT`)
