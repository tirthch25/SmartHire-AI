<div align="center">

# 🤖 SmartHire AI

### *Land your dream job — before anyone else does.*

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=22&pause=1000&color=6366F1&center=true&vCenter=true&width=600&lines=AI-Powered+ATS+Resume+Analyzer;Semantic+Job+Matching+Engine;Interview+Prep+%26+Cover+Letter+Generator;Built+with+FastAPI+%2B+Next.js+16+%2B+Gemini" alt="Typing SVG" />
</p>

<p align="center">
  <a href="https://github.com/tirthch25/SmartHire-AI/actions/workflows/ci.yml">
    <img src="https://github.com/tirthch25/SmartHire-AI/actions/workflows/ci.yml/badge.svg" alt="CI Status"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=flat&logo=nextdotjs&logoColor=white"/>
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black"/>
  <img src="https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/Gemini-2.0_Flash-4285F4?style=flat&logo=google&logoColor=white"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-F59E0B?style=flat"/>
</p>

<p align="center">
  <a href="#-quick-start-docker"><strong>🚀 Quick Start</strong></a> ·
  <a href="#-features"><strong>✨ Features</strong></a> ·
  <a href="#-architecture"><strong>🏗️ Architecture</strong></a> ·
  <a href="#-api-reference"><strong>📡 API Docs</strong></a> ·
  <a href="#-deployment"><strong>☁️ Deploy</strong></a>
</p>

---

> **SmartHire AI** is a full-stack, production-grade platform that turbocharges your job search with Google Gemini-powered resume analysis, semantic job matching, interview coaching, and tailored cover letters — all in one sleek dashboard.

</div>

---

## 📋 Table of Contents

- [🌟 Why SmartHire AI?](#-why-smarthire-ai)
- [✨ Features](#-features)
- [🏗️ Architecture](#-architecture)
- [⚙️ ATS Score Engine](#-ats-score-engine)
- [🛠️ Tech Stack](#-tech-stack)
- [📁 Project Structure](#-project-structure)
- [🚀 Quick Start (Docker)](#-quick-start-docker)
- [💻 Local Development](#-local-development)
- [🔐 Environment Variables](#-environment-variables)
- [📡 API Reference](#-api-reference)
- [🧪 Running Tests](#-running-tests)
- [☁️ Deployment](#-deployment)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)

---

## 🌟 Why SmartHire AI?

Most resumes are **rejected by ATS bots before a human ever sees them**. SmartHire AI flips the script:

| Without SmartHire AI | With SmartHire AI |
|---|---|
| ❌ Resume rejected by ATS filters | ✅ ATS score with exact fix suggestions |
| ❌ Apply and wonder why no callbacks | ✅ Semantic match score vs. job description |
| ❌ Generic cover letters | ✅ Tone-customized, AI-written cover letters |
| ❌ Blind interview preparation | ✅ AI-generated Q&A tailored to the role |
| ❌ No idea what skills you're missing | ✅ Skill gap analysis with learning resources |

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 📊 ATS Resume Scoring
5-component weighted engine analyzing keyword density, formatting, section completeness, skills overlap, and semantic experience relevance. Get a score out of 100 with actionable fixes.

### 🧠 AI Resume Parsing
Google Gemini 2.0 Flash extracts structured entities — name, email, phone, skills, work experience, education — from any PDF resume automatically.

### 🎯 Semantic Job Matching
Multi-dimensional matching using `SentenceTransformers` + Supabase `pgvector` embeddings for experience similarity, plus direct and fuzzy skills overlap scoring.

</td>
<td width="50%">

### 🕳️ Skill Gap Analysis
Instantly see which skills are missing for a target role, ranked by importance, with Gemini-curated learning resources and estimated timeline.

### 🎤 Interview Prep Coach
Generates 4 categories × 3 difficulty levels of interview questions with hints, sample answers, and follow-up questions — all tailored to your resume + job description.

### ✉️ Cover Letter Generator
Choose your tone (Professional · Confident · Enthusiastic · Formal), get a beautifully written cover letter, edit inline, and export as a polished PDF.

</td>
</tr>
<tr>
<td width="50%">

### 📈 Analytics Dashboard
Track your ATS score trends over time, see component-level averages, monitor improvement velocity, and review your activity feed.

</td>
<td width="50%">

### 🔒 Secure JWT Auth
15-minute access tokens + 7-day refresh tokens stored in Redis. Rate limiting on all sensitive endpoints. CORS-protected API.

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Next.js 16 Frontend (Vercel)                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │Dashboard │  │  Resume  │  │   Jobs /  │  │  Interview / │  │
│  │Analytics │  │  Upload  │  │  Matching │  │ Cover Letter │  │
│  └──────────┘  └──────────┘  └───────────┘  └──────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │  REST API  ·  JWT Bearer Tokens
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend (Vercel)                       │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  /auth  /resume  /ats  /job  /interview  /cover-letter     │ │
│  │                    /dashboard  /health                     │ │
│  └─────────────────────┬──────────────────────────────────────┘ │
│                         │  Celery Task Queue  (Redis broker)    │
│  ┌──────────────────────▼──────────────────────────────────────┐│
│  │                     AI Services Layer                       ││
│  │  pdf_parser ──► resume_parser ──► ats_scorer                ││
│  │  embedding_service ──► job_matcher ──► skill_gap_analyzer   ││
│  │  interview_generator ──► cover_letter_generator             ││
│  │  pdf_export_service                                         ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
    ┌────▼────┐   ┌─────▼────┐  ┌─────▼────┐  ┌─────▼────┐
    │PostgreSQL│   │  Redis   │  │ Vercel  │  │pgvector  │
    │(Supabase)│   │ Cache +  │  │  Blob   │  │ pgvector │
    │   ORM   │   │  Queue   │  │  Files  │  │  Vector  │
    └─────────┘   └──────────┘  └─────────┘  └──────────┘
```

### 🔄 Resume Processing Flow

```
📄 User uploads PDF
        │
        ▼
  FastAPI endpoint
  ├─ Upload to Vercel Blob
  └─ Create DB record (status: pending)
        │
        ▼
  🚀 Celery task dispatched (task_id → frontend polling)
        │
  ┌─────┴──────────────────────────────┐
  │  pdfplumber  ─────► text extraction│
  │  Gemini 2.0  ─────► entity parsing │
  │  MiniLM-L6   ─────► embedding gen  │
  │  Supabase pgvector ─► vector storage │
  └─────────────────────────────────────┘
        │
        ▼
  ✅ Resume status: completed
        │
        ▼
  🎯 ATS Analysis (resume_id + job_id)
  ├─ 30%  Keyword Match    (TF-IDF + regex)
  ├─ 20%  Skills Match     (direct + fuzzy)
  ├─ 20%  Experience       (semantic similarity)
  ├─ 15%  Formatting       (bullets, length, achievements)
  └─ 15%  Section Check    (required sections present)
        │
        ▼
  📊 Overall ATS Score → PostgreSQL → Frontend
```

---

## ⚙️ ATS Score Engine

<div align="center">

| Component | Weight | How It Works |
|-----------|:------:|---|
| 🔑 **Keyword Match** | **30%** | TF-IDF frequency analysis + regex overlap with job description keywords |
| 💼 **Skills Match** | **20%** | Direct skill match + fuzzy string matching for variations |
| 🧭 **Experience Relevance** | **20%** | Semantic cosine similarity via `all-MiniLM-L6-v2` embeddings |
| 🎨 **Formatting Quality** | **15%** | Bullet density, section length, quantified achievements detection |
| 📋 **Section Completeness** | **15%** | Presence check for Summary, Experience, Education, Skills, Contact |

</div>

```
Score Bands:
  🟢  75 – 100  →  Strong     — High chance of passing ATS filters
  🟡  50 –  74  →  Moderate   — Improvements recommended
  🔴   0 –  49  →  Low        — Significant rework needed
```

---

## 🛠️ Tech Stack

<div align="center">

### Backend
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![Vercel Blob](https://img.shields.io/badge/Vercel_Blob-000000?style=for-the-badge&logo=vercel&logoColor=white)

### AI / ML
![Google Gemini](https://img.shields.io/badge/Gemini_2.0_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)
![HuggingFace](https://img.shields.io/badge/SentenceTransformers-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)
![pgvector](https://img.shields.io/badge/pgvector-Supabase-3FCF8E?style=for-the-badge&logo=supabase)

### Frontend
![Next.js](https://img.shields.io/badge/Next.js_16-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)

### Infrastructure
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3FCF8E?style=for-the-badge&logo=supabase&logoColor=white)

</div>

---

## 📁 Project Structure

```
SmartHire-AI/
│
├── 🐍 backend/
│   ├── app/
│   │   ├── api/v1/               # 6 REST routers
│   │   │   ├── auth.py           # Register / Login / Refresh
│   │   │   ├── resume.py         # Upload / List / Delete
│   │   │   ├── ats.py            # Analyze / Score
│   │   │   ├── job.py            # Create / Match / Skill-Gap
│   │   │   ├── interview.py      # Generate questions
│   │   │   └── cover_letter.py   # Generate / Export PDF
│   │   ├── core/                 # Config, DB, Redis, Blob, Security
│   │   ├── models/               # SQLAlchemy ORM (6 models)
│   │   ├── schemas/              # Pydantic schemas (6 modules)
│   │   ├── services/             # 10 AI service modules
│   │   │   ├── pdf_parser.py
│   │   │   ├── resume_parser.py
│   │   │   ├── ats_scorer.py
│   │   │   ├── embedding_service.py
│   │   │   ├── job_matcher.py
│   │   │   ├── skill_gap_analyzer.py
│   │   │   ├── interview_generator.py
│   │   │   ├── cover_letter_generator.py
│   │   │   ├── pdf_export_service.py
│   │   │   └── analytics_service.py
│   │   └── workers/              # Celery app + 5 async tasks
│   ├── alembic/                  # DB migrations
│   ├── Dockerfile
│   └── requirements.txt
│
├── ⚛️  frontend/                  # Next.js 16 + React 19 + TypeScript
│   ├── src/
│   │   ├── app/                  # 8 Next.js App Router pages
│   │   │   ├── page.tsx          # Landing / home
│   │   │   ├── login/
│   │   │   ├── dashboard/
│   │   │   ├── resume/
│   │   │   ├── jobs/
│   │   │   ├── interview/
│   │   │   ├── cover-letter/
│   │   │   └── profile/          # Account settings & usage stats
│   │   ├── components/           # AppShell, Sidebar, Toast, ScoreRing…
│   │   └── lib/                  # API client, auth helpers
│   ├── Dockerfile
│   └── package.json
│
├── 🧪 tests/
│   └── backend/                  # 6 pytest test suites
│
├── 📚 docs/                      # Architecture, API, DB Schema, Deployment, Setup Guide
├── 🔧 .github/workflows/         # CI + database migration and Vercel deployment
├── 🐳 docker-compose.yml
├── 🐳 docker-compose.prod.yml
├── frontend/.env.example         # safe Next.js client configuration template
├── .env.example                  # safe backend/local development template
└── pytest.ini
```

---

## 🚀 Quick Start (Docker)

### Prerequisites

Before you begin, make sure you have:
- 🐳 [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- 🔑 [Google Gemini API key](https://aistudio.google.com/app/apikey) (free tier works)
- ▲ [Vercel account](https://vercel.com) with a Blob store created (free tier: 500 MB)
- 🐘 PostgreSQL connection string ([Supabase](https://supabase.com) project)

### 1️⃣ Clone & Configure

```bash
git clone https://github.com/tirthch25/SmartHire-AI.git
cd SmartHire-AI

# Copy the backend and frontend environment templates
cp .env.example .env
cp frontend/.env.example frontend/.env.local

# Add your local Gemini key and a generated SECRET_KEY to .env.
# Set the Supabase URL and publishable key in frontend/.env.local.
# Keep production credentials in Vercel/GitHub environment settings.
```

### 2️⃣ Launch All Services

The `docker-compose.yml` now includes the **Next.js frontend** — everything starts with one command:

```bash
docker compose up --build
```

| 🟢 Service | Port | URL |
|---|---|---|
| 🌐 Next.js Frontend | `3000` | http://localhost:3000 |
| ⚡ FastAPI API | `8000` | http://localhost:8000 |
| 🌸 Celery Flower | `5555` | http://localhost:5555 |
| 🐘 PostgreSQL | `5432` | — |
| ⚡ Redis | `6379` | — |

### 3️⃣ Run Database Migrations

```bash
docker compose exec api alembic upgrade head
```

### 4️⃣ Open & Explore

| Link | What's there |
|---|---|
| 🌐 http://localhost:3000 | The SmartHire AI app |
| 📖 http://localhost:8000/api/docs | Swagger interactive API docs |
| 🌸 http://localhost:5555 | Celery task monitor (Flower) |

---

## 💻 Local Development

### 🐍 Backend

```bash
cd backend

# Set up virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
# OR
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Start FastAPI with hot-reload
uvicorn app.main:app --reload --port 8000

# Start Celery worker (new terminal)
celery -A app.workers.celery_app worker --loglevel=info \
  --queues=resume,ats,ai,export,default

# Monitor tasks in browser (new terminal)
celery -A app.workers.celery_app flower --port=5555
```

### ⚛️ Frontend

> Requires **Node.js 20 LTS** · Next.js 16 · React 19

```bash
cd frontend
npm install
npm run dev       # → http://localhost:3000
```

---

## 🔐 Environment Variables

Keep local settings in ignored env files and production secrets in the deployment provider. The committed example files contain placeholders and safe local defaults only.

| File | Purpose | Commit it? |
|---|---|---|
| `.env.example` | Backend and Docker local-development template | Yes |
| `.env` | Local backend settings; use local PostgreSQL and Redis during development | No |
| `frontend/.env.example` | Safe Next.js client configuration template | Yes |
| `frontend/.env.local` | Supabase project URL, publishable key, and frontend settings | No |
| `.env.local` | Local Vercel CLI values such as its short-lived OIDC token | No |

Create local files from the templates:

```powershell
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env.local
```

The root `DATABASE_URL` should point to local PostgreSQL for local development. For deployment, set the Supabase Session Pooler URL in Vercel and as the GitHub Actions `DATABASE_URL` secret. Do not put production credentials in `.env.example` or copy the old Neon URL into deployment settings. Keep `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `BLOB_READ_WRITE_TOKEN`, `GEMINI_API_KEY`, and `SECRET_KEY` server-side; never give secrets a `NEXT_PUBLIC_` prefix.

`NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` are public client configuration values. They belong in `frontend/.env.local` for local development and in the Vercel project environment for Preview and Production. See [`docs/deployment.md`](docs/deployment.md) for production setup.

## 📡 API Reference

Full interactive docs at **`/api/docs`** (Swagger UI) · **`/api/redoc`** (ReDoc) when the server is running.

### Endpoints at a Glance

| Method | Endpoint | Description |
|:------:|---|---|
| `POST` | `/api/v1/auth/register` | Create new user account |
| `POST` | `/api/v1/auth/login` | Authenticate → access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Rotate access token |
| `POST` | `/api/v1/auth/logout` | Invalidate refresh token |
| `GET`  | `/api/v1/auth/me` | Get current user profile |
| `POST` | `/api/v1/resume/upload` | Upload PDF resume (→ Celery pipeline) |
| `GET`  | `/api/v1/resume/list` | List all user resumes |
| `GET`  | `/api/v1/resume/{id}` | Get resume metadata & parsed data |
| `DELETE` | `/api/v1/resume/{id}` | Delete a resume |
| `GET`  | `/api/v1/resume/{id}/download` | Authenticated download route for private PDF |
| `POST` | `/api/v1/ats/analyze` | Trigger ATS scoring (→ Celery) |
| `GET`  | `/api/v1/ats/score/{resume_id}` | Fetch latest ATS score breakdown |
| `GET`  | `/api/v1/ats/status/{task_id}` | Poll Celery task status |
| `GET`  | `/api/v1/ats/history` | List all analyses (paginated) |
| `GET`  | `/api/v1/ats/export/{analysis_id}` | Export ATS report as PDF |
| `POST` | `/api/v1/job/create` | Save a job description |
| `GET`  | `/api/v1/job/list` | List saved jobs |
| `DELETE` | `/api/v1/job/{job_id}` | Delete a job |
| `POST` | `/api/v1/job/match` | Get semantic match score |
| `GET`  | `/api/v1/job/skill-gap` | Skill gap analysis with resources |
| `POST` | `/api/v1/interview/generate` | Generate interview questions (→ Celery) |
| `GET`  | `/api/v1/interview/{session_id}` | Get generated questions |
| `GET`  | `/api/v1/interview/list` | List all interview sessions |
| `POST` | `/api/v1/cover-letter/generate` | Generate cover letter (→ Celery) |
| `PUT`  | `/api/v1/cover-letter/{id}` | Edit a cover letter |
| `GET`  | `/api/v1/cover-letter/list` | List all cover letters |
| `GET`  | `/api/v1/cover-letter/{id}/export` | Export cover letter as PDF |
| `GET`  | `/api/v1/dashboard/stats` | Dashboard summary stats |
| `GET`  | `/api/v1/dashboard/analytics` | Score trends + chart data |
| `GET`  | `/api/v1/dashboard/activity` | Recent activity feed |
| `GET`  | `/health` | Service health check |

> 🔒 All non-auth endpoints require: `Authorization: Bearer <access_token>`

---

## 🧪 Running Tests

```bash
# From project root
pip install -r backend/requirements.txt pytest-asyncio httpx

# Run entire test suite
pytest

# Verbose mode with test names
pytest -v

# Single file
pytest tests/backend/test_auth.py -v

# With HTML coverage report
pytest --cov=backend/app --cov-report=html
open htmlcov/index.html

# Skip integration tests (no external services needed)
pytest -m "not integration"
```

### Test Coverage

| Module | Tests |
|---|---|
| `test_auth.py` | Register, login, refresh, logout, JWT validation |
| `test_resume.py` | Upload, list, delete, download, parsing pipeline |
| `test_ats.py` | Score components, weighted calculation, PDF export |
| `test_job_match.py` | Semantic matching, skill overlap, skill gap |
| `test_cover_letter.py` | Generation, tone customization, PDF export |
| `test_dashboard.py` | Stats aggregation, analytics trends, activity feed |

---

## ☁️ Deployment

### Full stack → Vercel

Import the repository with its root as the project root. Enable the **Services** framework and confirm your Vercel team has access to Services and Daemons. The root `vercel.json` deploys the Next.js app, FastAPI API, and Celery daemon under one Vercel project. See [`docs/deployment.md`](docs/deployment.md) for the required environment variables and rollout steps.

### Database → Supabase

Create a Supabase project, use its Session Pooler connection URL as `DATABASE_URL`, and run `alembic upgrade head`. Migration `002_pgvector_embeddings` stores semantic vectors in Supabase PostgreSQL.

### ☁️ File Storage → Vercel Blob

1. Go to [vercel.com](https://vercel.com) → your project → **Storage** tab → **Create Blob Store**
2. Connect the private store to the project. Vercel's Python SDK uses project OIDC credentials; configure `BLOB_READ_WRITE_TOKEN` for local or external environments.
3. Authenticated API routes check the user's JWT and ownership before streaming each private file.

### 🔑 Required GitHub Secrets

| Secret | Used by |
|---|---|
| `SECRET_KEY` | Backend JWT signing |
| `DATABASE_URL` | Supabase PostgreSQL Session Pooler URL |
| `GEMINI_API_KEY` | AI features (Vercel environment) |
| `BLOB_READ_WRITE_TOKEN` | Vercel Blob (Vercel environment) |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Managed Redis (Vercel environment) |
| `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | Full project deployment workflow |

---

## 🤝 Contributing

Contributions are what make the open-source community such an amazing place. Any contributions you make are **greatly appreciated**!

1. 🍴 Fork the project
2. 🌿 Create your feature branch (`git checkout -b feat/amazing-feature`)
3. 💾 Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. 📤 Push to the branch (`git push origin feat/amazing-feature`)
5. 🔃 Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## 📜 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ by [Tirth Chankeshwara](https://github.com/tirthch25)**

*If SmartHire AI helped you land a job, give it a ⭐ — it means the world!*

<a href="https://github.com/tirthch25/SmartHire-AI">
  <img src="https://img.shields.io/github/stars/tirthch25/SmartHire-AI?style=social" alt="GitHub Stars"/>
</a>

</div>
