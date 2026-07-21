<div align="center">

# 🤖 SmartHire AI

### *Land your dream job — before anyone else does.*

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=22&pause=1000&color=6366F1&center=true&vCenter=true&width=600&lines=AI-Powered+ATS+Resume+Analyzer;Semantic+Job+Matching+Engine;Interview+Prep+%26+Cover+Letter+Generator;Built+with+FastAPI+%2B+Next.js+%2B+Gemini" alt="Typing SVG" />
</p>

<p align="center">
  <a href="https://github.com/tirthch25/SmartHire-AI/actions/workflows/ci.yml">
    <img src="https://github.com/tirthch25/SmartHire-AI/actions/workflows/ci.yml/badge.svg" alt="CI Status"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/Next.js-14-000000?style=flat&logo=nextdotjs&logoColor=white"/>
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
Multi-dimensional matching using `SentenceTransformers` + `ChromaDB` embeddings for experience similarity, plus direct and fuzzy skills overlap scoring.

</td>
<td width="50%">

### 🕳️ Skill Gap Analysis
Instantly see which skills are missing for a target role, ranked by importance, with Gemini-curated learning resources and estimated timeline.

### 🎤 Interview Prep Coach
Generates 4 categories × 3 difficulty levels of interview questions with hints, sample answers, and follow-up questions — all tailored to your resume + job description.

### ✉️ Cover Letter Generator
Choose your tone (Professional · Enthusiastic · Concise), get a beautifully written cover letter, edit inline, and export as a polished PDF.

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
│                   Next.js 14 Frontend (Vercel)                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────────┐  │
│  │Dashboard │  │  Resume  │  │   Jobs /  │  │  Interview / │  │
│  │Analytics │  │  Upload  │  │  Matching │  │ Cover Letter │  │
│  └──────────┘  └──────────┘  └───────────┘  └──────────────┘  │
└──────────────────────────┬──────────────────────────────────────┘
                           │  REST API  ·  JWT Bearer Tokens
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend (Render)                       │
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
    ┌────▼────┐   ┌─────▼────┐  ┌────▼────┐  ┌─────▼────┐
    │PostgreSQL│   │  Redis   │  │  AWS S3 │  │ ChromaDB │
    │  (Neon) │   │ Cache +  │  │  Files  │  │Embeddings│
    │   ORM   │   │  Queue   │  │  Store  │  │  Vector  │
    └─────────┘   └──────────┘  └─────────┘  └──────────┘
```

### 🔄 Resume Processing Flow

```
📄 User uploads PDF
        │
        ▼
  FastAPI endpoint
  ├─ Upload to AWS S3
  └─ Create DB record (status: pending)
        │
        ▼
  🚀 Celery task dispatched (task_id → frontend polling)
        │
  ┌─────┴──────────────────────────────┐
  │  pdfplumber  ─────► text extraction│
  │  Gemini 2.0  ─────► entity parsing │
  │  MiniLM-L6   ─────► embedding gen  │
  │  ChromaDB    ─────► vector storage │
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
![AWS](https://img.shields.io/badge/AWS_S3-FF9900?style=for-the-badge&logo=amazons3&logoColor=white)

### AI / ML
![Google Gemini](https://img.shields.io/badge/Gemini_2.0_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)
![HuggingFace](https://img.shields.io/badge/SentenceTransformers-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black)
![ChromaDB](https://img.shields.io/badge/ChromaDB-Vector_DB-8B5CF6?style=for-the-badge)

### Frontend
![Next.js](https://img.shields.io/badge/Next.js_14-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)

### Infrastructure
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)
![Render](https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=black)
![Neon](https://img.shields.io/badge/Neon_DB-00E699?style=for-the-badge&logo=neon&logoColor=black)

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
│   │   ├── core/                 # Config, DB, Redis, S3, Security
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
├── ⚛️  frontend/
│   ├── src/
│   │   ├── app/                  # 7 Next.js App Router pages
│   │   │   ├── page.tsx          # Landing / home
│   │   │   ├── login/
│   │   │   ├── dashboard/
│   │   │   ├── resume/
│   │   │   ├── jobs/
│   │   │   ├── interview/
│   │   │   └── cover-letter/
│   │   ├── components/           # AppShell, Sidebar, Toast, ScoreRing…
│   │   └── lib/                  # API client, auth helpers
│   ├── Dockerfile
│   └── package.json
│
├── 🧪 tests/
│   └── backend/                  # 7 pytest test suites
│
├── 📚 docs/                      # Architecture, API, DB Schema, Setup
├── 🔧 .github/workflows/         # CI + backend + frontend deploy
├── 🐳 docker-compose.yml
├── 🐳 docker-compose.prod.yml
├── .env.example                  # ← copy to .env and fill in
└── pytest.ini
```

---

## 🚀 Quick Start (Docker)

### Prerequisites

Before you begin, make sure you have:
- 🐳 [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- 🔑 [Google Gemini API key](https://aistudio.google.com/app/apikey) (free tier works)
- ☁️ AWS account with an S3 bucket
- 🐘 PostgreSQL connection string ([Neon](https://neon.tech) free tier recommended)

### 1️⃣ Clone & Configure

```bash
git clone https://github.com/tirthch25/SmartHire-AI.git
cd SmartHire-AI

# Copy the environment template
cp .env.example .env

# Open .env and fill in your credentials
# (at minimum: GEMINI_API_KEY, DATABASE_URL, AWS keys)
```

### 2️⃣ Launch All Services

```bash
docker compose up --build
```

| 🟢 Service | Port | URL |
|---|---|---|
| ⚡ FastAPI API | `8000` | http://localhost:8000 |
| 🌐 Next.js Frontend | `3000` | http://localhost:3000 |
| 🌸 Celery Flower | `5555` | http://localhost:5555 |
| 🐘 PostgreSQL | `5432` | — |
| ⚡ Redis | `6379` | — |
| 🔮 ChromaDB | `8001` | — |

### 3️⃣ Run Database Migrations

```bash
docker compose exec api alembic upgrade head
```

### 4️⃣ Open & Explore

| Link | What's there |
|---|---|
| 🌐 http://localhost:3000 | The SmartHire AI app |
| 📖 http://localhost:8000/docs | Swagger interactive API docs |
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

```bash
cd frontend
npm install
npm run dev       # → http://localhost:3000
```

---

## 🔐 Environment Variables

Copy `.env.example` → `.env` and fill in:

```env
# ── App ────────────────────────────────────────────────────────
APP_ENV=development
SECRET_KEY=generate-with-openssl-rand-hex-32
DEBUG=true

# ── Database (Neon recommended) ────────────────────────────────
DATABASE_URL=postgresql+asyncpg://user:pass@host/smarthire_db?sslmode=require

# ── Redis ──────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# ── AWS S3 ─────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_REGION=us-east-1
AWS_S3_BUCKET_NAME=smarthire-ai

# ── Google Gemini AI ───────────────────────────────────────────
GEMINI_API_KEY=your-gemini-api-key      # 🔑 most important!
GEMINI_MODEL=gemini-2.0-flash

# ── ChromaDB ───────────────────────────────────────────────────
CHROMA_HOST=localhost
CHROMA_PORT=8001

# ── CORS ───────────────────────────────────────────────────────
ALLOWED_ORIGINS=http://localhost:3000,https://your-domain.vercel.app
```

> 💡 **Tip:** Generate a secure `SECRET_KEY` with:
> ```bash
> openssl rand -hex 32
> ```

---

## 📡 API Reference

Full interactive docs at **`/docs`** (Swagger UI) · **`/redoc`** (ReDoc) when the server is running.

### Endpoints at a Glance

| Method | Endpoint | Description |
|:------:|---|---|
| `POST` | `/api/v1/auth/register` | Create new user account |
| `POST` | `/api/v1/auth/login` | Authenticate → access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | Rotate access token |
| `GET`  | `/api/v1/auth/me` | Get current user profile |
| `POST` | `/api/v1/resume/upload` | Upload PDF resume (→ Celery pipeline) |
| `GET`  | `/api/v1/resume/list` | List all user resumes |
| `DELETE` | `/api/v1/resume/{id}` | Delete a resume |
| `POST` | `/api/v1/ats/analyze` | Trigger ATS scoring (→ Celery) |
| `GET`  | `/api/v1/ats/score/{resume_id}` | Fetch latest ATS score breakdown |
| `POST` | `/api/v1/job/create` | Save a job description |
| `POST` | `/api/v1/job/match` | Get semantic match score |
| `GET`  | `/api/v1/job/skill-gap` | Skill gap analysis with resources |
| `POST` | `/api/v1/interview/generate` | Generate interview questions (→ Celery) |
| `POST` | `/api/v1/cover-letter/generate` | Generate cover letter (→ Celery) |
| `GET`  | `/api/v1/cover-letter/{id}/export` | Export cover letter as PDF |
| `GET`  | `/api/v1/dashboard/stats` | Dashboard summary stats |
| `GET`  | `/api/v1/dashboard/analytics` | Score trends + chart data |
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
| `test_auth.py` | Register, login, refresh, JWT validation |
| `test_resume.py` | Upload, list, delete, parsing pipeline |
| `test_ats.py` | Score components, weighted calculation |
| `test_job_match.py` | Semantic matching, skill overlap |
| `test_cover_letter.py` | Generation, tone customization, PDF export |
| `test_dashboard.py` | Stats aggregation, analytics trends |

---

## ☁️ Deployment

### 🔧 Backend → Render

1. Create a new **Web Service** on [Render](https://render.com)
2. Connect your GitHub repository
3. **Build Command:** `pip install -r backend/requirements.txt`
4. **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add all env vars from `.env.example` in Render dashboard
6. Set `RENDER_DEPLOY_HOOK_URL` in GitHub Secrets for auto-deploy on push

### 🌐 Frontend → Vercel

1. Import your GitHub repo at [vercel.com/new](https://vercel.com/new)
2. Set **Root Directory** → `frontend`
3. Add env var: `NEXT_PUBLIC_API_URL=https://your-render-app.onrender.com/api/v1`
4. Set GitHub Secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`

### 🐘 Database → Neon

1. Create a free project at [neon.tech](https://neon.tech)
2. Copy connection string → `DATABASE_URL` in your env
3. Apply schema: `alembic upgrade head`

### 🔑 Required GitHub Secrets

| Secret | Used by |
|---|---|
| `SECRET_KEY` | Backend JWT signing |
| `DATABASE_URL` | Production PostgreSQL |
| `GEMINI_API_KEY` | All AI features |
| `AWS_ACCESS_KEY_ID` | S3 file storage |
| `AWS_SECRET_ACCESS_KEY` | S3 file storage |
| `REDIS_URL` | Cache + task queue |
| `RENDER_DEPLOY_HOOK_URL` | Backend auto-deploy |
| `VERCEL_TOKEN` | Frontend deploy |
| `VERCEL_ORG_ID` | Frontend deploy |
| `VERCEL_PROJECT_ID` | Frontend deploy |
| `NEXT_PUBLIC_API_URL` | Frontend API target |

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

**Built with ❤️ by [Tirth Chauhan](https://github.com/tirthch25)**

*If SmartHire AI helped you land a job, give it a ⭐ — it means the world!*

<a href="https://github.com/tirthch25/SmartHire-AI">
  <img src="https://img.shields.io/github/stars/tirthch25/SmartHire-AI?style=social" alt="GitHub Stars"/>
</a>

</div>
