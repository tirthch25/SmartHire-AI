# SmartHire AI — System Architecture

## Table of Contents
1. [System Overview](#1-system-overview)
2. [High-Level Architecture Diagram](#2-high-level-architecture-diagram)
3. [Request Flow — PDF Upload & ATS Analysis](#3-request-flow--pdf-upload--ats-analysis)
4. [Database Entity-Relationship Diagram](#4-database-entity-relationship-diagram)
5. [Celery Task Dependency Graph](#5-celery-task-dependency-graph)
6. [Component Responsibilities](#6-component-responsibilities)
7. [Security Architecture](#7-security-architecture)
8. [Data Flow — AI Pipeline](#8-data-flow--ai-pipeline)

---

## 1. System Overview

SmartHire AI is a multi-tier web application with clearly separated concerns:

| Tier | Technology | Deployment |
|------|-----------|-----------|
| **Frontend** | Next.js 14 (App Router) + TypeScript + TailwindCSS | Vercel |
| **Backend API** | FastAPI (Python 3.11) | Vercel |
| **Task Workers** | Celery 5.4 | Vercel (background worker) |
| **Primary Database** | PostgreSQL | Supabase |
| **Cache + Broker** | Redis 7 | Redis Cloud / Upstash |
| **Vector Database** | pgvector | Vercel (separate service) |
| **File Storage** | Private Vercel Blob | Vercel |
| **AI Models** | Gemini 2.0 Flash + SentenceTransformers (all-MiniLM-L6-v2) | API / Embedded |

---

## 2. High-Level Architecture Diagram

```mermaid
graph TB
    subgraph Client["Client Layer"]
        Browser["Browser\n(Next.js 14 App)"]
    end

    subgraph CDN["CDN / Edge"]
        Vercel["Vercel Edge Network"]
    end

    subgraph API["API Layer (Vercel)"]
        FastAPI["FastAPI Server\n:8000"]
        RateLimiter["SlowAPI Rate Limiter\n(Redis-backed)"]
        JWTMiddleware["JWT Auth Middleware"]
    end

    subgraph Workers["Worker Layer (Vercel)"]
        CeleryWorker["Celery Worker\n(async tasks)"]
        CeleryFlower["Flower Monitor\n:5555"]
    end

    subgraph DataLayer["Data Layer"]
        Postgres["PostgreSQL\n(Supabase)\nPrimary DB"]
        Redis["Redis\nCache + Broker"]
        Supabase pgvector["Supabase pgvector\nVector Store"]
        S3["Private Vercel Blob\nFile Storage"]
    end

    subgraph AILayer["AI Layer"]
        Gemini["Google Gemini\n2.0 Flash API"]
        SentenceTransformers["SentenceTransformers\nall-MiniLM-L6-v2\n(local embedding)"]
    end

    Browser --> Vercel
    Vercel --> FastAPI
    FastAPI --> RateLimiter
    FastAPI --> JWTMiddleware
    FastAPI --> Postgres
    FastAPI --> Redis
    FastAPI --> S3
    FastAPI --> CeleryWorker

    CeleryWorker --> Redis
    CeleryWorker --> Postgres
    CeleryWorker --> S3
    CeleryWorker --> Supabase pgvector
    CeleryWorker --> Gemini
    CeleryWorker --> SentenceTransformers

    FastAPI -.->|query vectors| Supabase pgvector
    CeleryFlower -.->|monitor| CeleryWorker
```

---

## 3. Request Flow — PDF Upload & ATS Analysis

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant N as Next.js Frontend
    participant F as FastAPI
    participant S3 as Vercel Blob
    participant R as Redis
    participant C as Celery Worker
    participant G as Gemini API
    participant ST as SentenceTransformers
    participant CH as Supabase pgvector
    participant DB as PostgreSQL

    U->>N: Select PDF file + job description
    N->>F: POST /resume/upload (multipart)
    F->>F: Validate JWT token
    F->>F: Validate file (size ≤10MB, type=PDF)
    F->>S3: Upload raw PDF → /resumes/{user_id}/{uuid}.pdf
    S3-->>F: blob pathname returned
    F->>DB: INSERT resume (status='pending', s3_key)
    F->>C: dispatch process_resume_upload.delay(resume_id)
    F-->>N: {resume_id, task_id, status:'pending'}
    N->>U: Show progress UI (polling task_id)

    loop Poll every 2s
        N->>F: GET /ats/status/{task_id}
        F->>R: GET celery-task-meta:{task_id}
        R-->>F: {state, progress}
        F-->>N: {state, progress}
    end

    Note over C: Celery Worker Processing
    C->>S3: Download PDF bytes
    C->>C: pdfplumber → raw_text extraction
    C->>G: Extract structured entities (Name, Email, Skills, etc.)
    G-->>C: parsed_data JSON
    C->>ST: Encode resume text → embedding vector
    C->>CH: Store embedding in 'resumes' collection
    C->>DB: UPDATE resume (status='completed', parsed_data, raw_text)

    Note over C: ATS Scoring
    C->>G: Parse job description → required_skills
    C->>C: Keyword Match score (TF-IDF)
    C->>C: Formatting score (section detection)
    C->>C: Section Completeness score
    C->>ST: Skills Match score (cosine similarity)
    C->>CH: Experience Relevance (vector search)
    C->>C: Weighted sum → overall_score
    C->>DB: INSERT ats_analysis (all scores, detailed_report)
    C->>R: SET cache invalidation

    N->>F: GET /ats/score/{resume_id}
    F->>R: GET cache:ats:{resume_id}
    alt Cache miss
        F->>DB: SELECT ats_analysis
        F->>R: SET cache:ats:{resume_id} TTL=300s
    end
    F-->>N: Full ATS score response
    N->>U: Vercel score breakdown dashboard
```

---

## 4. Database Entity-Relationship Diagram

```mermaid
erDiagram
    USERS {
        uuid id PK
        varchar email UK
        varchar full_name
        varchar hashed_password
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    RESUMES {
        uuid id PK
        uuid user_id FK
        varchar filename
        varchar s3_key
        integer file_size
        text raw_text
        jsonb parsed_data
        varchar status
        varchar celery_task_id
        timestamptz created_at
    }

    JOBS {
        uuid id PK
        uuid user_id FK
        varchar title
        varchar company
        text description
        jsonb required_skills
        jsonb parsed_data
        timestamptz created_at
    }

    ATS_ANALYSES {
        uuid id PK
        uuid resume_id FK
        uuid job_id FK
        uuid user_id FK
        float overall_score
        float keyword_score
        float formatting_score
        float section_score
        float skills_score
        float experience_score
        jsonb detailed_report
        varchar report_s3_key
        varchar celery_task_id
        timestamptz created_at
    }

    COVER_LETTERS {
        uuid id PK
        uuid user_id FK
        uuid resume_id FK
        uuid job_id FK
        text content
        varchar tone
        varchar s3_key
        varchar celery_task_id
        timestamptz created_at
        timestamptz updated_at
    }

    INTERVIEW_SESSIONS {
        uuid id PK
        uuid user_id FK
        uuid resume_id FK
        uuid job_id FK
        jsonb questions
        varchar celery_task_id
        timestamptz created_at
    }

    USERS ||--o{ RESUMES : "owns"
    USERS ||--o{ JOBS : "creates"
    USERS ||--o{ ATS_ANALYSES : "has"
    USERS ||--o{ COVER_LETTERS : "generates"
    USERS ||--o{ INTERVIEW_SESSIONS : "conducts"
    RESUMES ||--o{ ATS_ANALYSES : "analyzed by"
    JOBS ||--o{ ATS_ANALYSES : "matched in"
    RESUMES ||--o{ COVER_LETTERS : "used in"
    JOBS ||--o{ COVER_LETTERS : "targeted for"
    RESUMES ||--o{ INTERVIEW_SESSIONS : "based on"
    JOBS ||--o{ INTERVIEW_SESSIONS : "prepared for"
```

---

## 5. Celery Task Dependency Graph

```mermaid
graph LR
    subgraph Triggers["API Triggers"]
        T1["POST /resume/upload"]
        T2["POST /ats/analyze"]
        T3["POST /cover-letter/generate"]
        T4["POST /interview/generate"]
        T5["GET /ats/export/{id}"]
    end

    subgraph Tasks["Celery Tasks (Redis Broker)"]
        W1["process_resume_upload\n─────────────\n• Download PDF from private Blob\n• Extract text (pdfplumber)\n• Parse entities (Gemini)\n• Embed text (SentenceTransformers)\n• Store in Supabase pgvector\n• Update DB status"]

        W2["generate_ats_analysis\n─────────────\n• Keyword Match (TF-IDF)\n• Formatting check\n• Section completeness\n• Skills similarity (ST)\n• Experience relevance (Supabase pgvector)\n• Store scores in DB"]

        W3["generate_cover_letter\n─────────────\n• Load resume + job data\n• Gemini generation\n• Store in DB"]

        W4["generate_interview_questions\n─────────────\n• Load resume + job data\n• Gemini multi-category gen\n• Store in DB"]

        W5["export_pdf_report\n─────────────\n• Fetch ATS analysis\n• Build PDF (ReportLab)\n• Upload PDF to private Blob\n• Return authenticated download route"]
    end

    subgraph Results["Result Backend (Redis)"]
        R["celery-task-meta:{task_id}\n{state, result, traceback}"]
    end

    T1 --> W1
    T2 --> W2
    W1 -.->|"auto-chains on completion"| W2
    T3 --> W3
    T4 --> W4
    T5 --> W5
    W2 -.->|"result available"| W5

    W1 --> R
    W2 --> R
    W3 --> R
    W4 --> R
    W5 --> R
```

---

## 6. Component Responsibilities

### FastAPI Backend
- **Auth module**: JWT issuance, validation, refresh, bcrypt hashing
- **Route handlers**: Input validation (Pydantic v2), auth guard, response shaping
- **Rate limiter**: SlowAPI with Redis storage — 60 req/min per user
- **Orchestration**: Dispatch Celery tasks, return task_id for polling
- **Cache layer**: Redis-backed response caching for analytics (5-min TTL)

### Celery Workers
- **Isolation**: All AI-heavy, long-running work runs outside the request cycle
- **Retry policy**: Max 3 retries with exponential backoff on transient failures
- **Progress updates**: Task state updated with custom `UPDATE` state + percentage
- **Concurrency**: 4 worker processes (configurable via `CELERY_CONCURRENCY`)

### Supabase pgvector
- **Collection: `resumes`** — one embedding per resume document
- **Collection: `jobs`** — one embedding per job description
- **Purpose**: Semantic similarity search for Skills Match and Experience Relevance scoring
- **Embedding model**: `all-MiniLM-L6-v2` (384-dim, runs locally in worker)

### Vercel Blob File Layout
```
smarthire-ai-bucket/
├── resumes/
│   └── {user_id}/
│       └── {resume_uuid}.pdf
├── reports/
│   └── {user_id}/
│       └── {analysis_uuid}_report.pdf
└── cover-letters/
    └── {user_id}/
        └── {letter_uuid}.pdf
```

---

## 7. Security Architecture

```mermaid
graph TD
    subgraph Auth["Authentication Flow"]
        Login["POST /auth/login\n(email + password)"] --> Hash["bcrypt.verify(password)"]
        Hash --> Issue["Issue JWT pair\n• access_token (15min)\n• refresh_token (7 days)"]
        Issue --> Store["Store refresh_token\nin Redis with TTL"]
    end

    subgraph Guard["Request Guard"]
        Req["Incoming Request"] --> Bearer["Extract Bearer token\nfrom Authorization header"]
        Bearer --> Verify["jwt.decode(token, SECRET_KEY)"]
        Verify --> |valid| Allow["Allow → inject current_user"]
        Verify --> |expired| Refresh["POST /auth/refresh\nExchange refresh_token"]
        Verify --> |invalid| Deny["401 Unauthorized"]
    end

    subgraph RateLimit["Rate Limiting"]
        RL["SlowAPI\n60 req/min per IP\n10 req/min on /auth/*\nRedis storage backend"]
    end

    subgraph InputVal["Input Validation"]
        IV["Pydantic v2\n• Type coercion\n• Field constraints\n• Custom validators\n• File type/size check"]
    end
```

**Security measures:**
- Passwords hashed with `bcrypt` (12 rounds)
- JWT signed with `HS256`, access token TTL = 15 minutes
- Refresh tokens stored in Redis (invalidated on logout)
- File validation: MIME type must be `application/pdf`, max 10 MB
- All inputs validated by Pydantic v2 before hitting business logic
- CORS restricted to `ALLOWED_ORIGINS` env var
- Private Blob files are streamed through authenticated, ownership-checked API routes

---

## 8. Data Flow — AI Pipeline

```mermaid
graph TD
    PDF["PDF File\n(uploaded by user)"] --> S3Up["Upload to Vercel Blob"]
    S3Up --> CeleryQ["Celery Queue\n(Redis broker)"]

    CeleryQ --> Extract["Text Extraction\npdfplumber"]
    Extract --> GeminiParse["Gemini 2.0 Flash\nStructured Entity Extraction"]
    GeminiParse --> ParsedData["Parsed Resume\n{name, email, phone,\nskills[], education[],\nexperience[], projects[],\ncertifications[]}"]

    ParsedData --> Embed["SentenceTransformers\nall-MiniLM-L6-v2\n→ 384-dim vector"]
    Embed --> PgvectorStore["Supabase pgvector\nresumes collection"]

    subgraph ATSScore["ATS Scoring Engine"]
        KW["Keyword Match\n30%\n(TF-IDF overlap)"]
        FMT["Formatting\n15%\n(section detection)"]
        SEC["Section Completeness\n15%\n(required sections)"]
        SKL["Skills Match\n20%\n(cosine similarity)"]
        EXP["Experience Relevance\n20%\n(Supabase pgvector vector search)"]
        TOTAL["Weighted Score\n0-100"]

        KW --> TOTAL
        FMT --> TOTAL
        SEC --> TOTAL
        SKL --> TOTAL
        EXP --> TOTAL
    end

    ParsedData --> ATSScore
    PgvectorStore -.->|vector search| EXP

    TOTAL --> Report["Detailed Report\n(JSONB in PostgreSQL)"]
    Report --> PDFExport["PDF Report\n(ReportLab → S3)"]
    Report --> Dashboard["Dashboard\n(Redis-cached analytics)"]
```
