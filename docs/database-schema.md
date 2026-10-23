# SmartHire AI — Database Schema

## Overview

SmartHire AI uses **PostgreSQL** as the primary relational database, hosted on **Supabase**.
UUIDs are used as primary keys throughout (via `gen_random_uuid()`).  
JSONB columns store semi-structured AI output (parsed data, report details, questions).

---

## Full Schema DDL

```sql
-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABLE: users
-- ============================================================
CREATE TABLE users (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255)    NOT NULL UNIQUE,
    full_name       VARCHAR(255)    NOT NULL,
    hashed_password VARCHAR(255)    NOT NULL,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  users                    IS 'Registered user accounts';
COMMENT ON COLUMN users.hashed_password    IS 'bcrypt hash, 12 rounds';
COMMENT ON COLUMN users.is_active          IS 'Soft-delete / account suspension flag';

-- ============================================================
-- TABLE: resumes
-- ============================================================
CREATE TABLE resumes (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        VARCHAR(255)    NOT NULL,
    s3_key          VARCHAR(512)    NOT NULL,
    file_size       INTEGER         NOT NULL CHECK (file_size > 0 AND file_size <= 10485760),
    raw_text        TEXT,
    parsed_data     JSONB,
    status          VARCHAR(50)     NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending','processing','completed','failed')),
    celery_task_id  VARCHAR(255),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  resumes               IS 'Uploaded PDF resumes with private Blob reference';
COMMENT ON COLUMN resumes.s3_key        IS 'Private Blob object reference: resumes/{user_id}/{uuid}.pdf';
COMMENT ON COLUMN resumes.file_size     IS 'File size in bytes, max 10MB enforced by CHECK';
COMMENT ON COLUMN resumes.parsed_data   IS 'Gemini-extracted structured entities (JSONB)';
COMMENT ON COLUMN resumes.status        IS 'Celery processing status';

-- ============================================================
-- TABLE: jobs
-- ============================================================
CREATE TABLE jobs (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255)    NOT NULL,
    company         VARCHAR(255),
    description     TEXT            NOT NULL,
    required_skills JSONB,
    parsed_data     JSONB,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  jobs                  IS 'Job descriptions saved by users for matching';
COMMENT ON COLUMN jobs.required_skills  IS 'Gemini-extracted list of required skills (string[])';
COMMENT ON COLUMN jobs.parsed_data      IS 'Full structured job requirements from Gemini';

-- ============================================================
-- TABLE: ats_analyses
-- ============================================================
CREATE TABLE ats_analyses (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id           UUID        NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    job_id              UUID        REFERENCES jobs(id) ON DELETE SET NULL,
    user_id             UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    overall_score       FLOAT       NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),
    keyword_score       FLOAT       NOT NULL CHECK (keyword_score >= 0 AND keyword_score <= 100),
    formatting_score    FLOAT       NOT NULL CHECK (formatting_score >= 0 AND formatting_score <= 100),
    section_score       FLOAT       NOT NULL CHECK (section_score >= 0 AND section_score <= 100),
    skills_score        FLOAT       NOT NULL CHECK (skills_score >= 0 AND skills_score <= 100),
    experience_score    FLOAT       NOT NULL CHECK (experience_score >= 0 AND experience_score <= 100),
    detailed_report     JSONB,
    report_s3_key       VARCHAR(512),
    celery_task_id      VARCHAR(255),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  ats_analyses                  IS 'ATS scoring results for resume-job pairs';
COMMENT ON COLUMN ats_analyses.overall_score    IS 'Weighted: KW(30)+FMT(15)+SEC(15)+SKL(20)+EXP(20)';
COMMENT ON COLUMN ats_analyses.detailed_report  IS 'Matched/missing keywords, issues, recommendations';
COMMENT ON COLUMN ats_analyses.report_s3_key    IS 'Private Blob reference for exported PDF report (nullable until exported)';

-- ============================================================
-- TABLE: cover_letters
-- ============================================================
CREATE TABLE cover_letters (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id       UUID            REFERENCES resumes(id) ON DELETE SET NULL,
    job_id          UUID            REFERENCES jobs(id) ON DELETE SET NULL,
    content         TEXT            NOT NULL,
    tone            VARCHAR(50)     NOT NULL DEFAULT 'professional'
                                    CHECK (tone IN ('professional','confident','enthusiastic','formal')),
    s3_key          VARCHAR(512),
    celery_task_id  VARCHAR(255),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  cover_letters         IS 'AI-generated cover letters';
COMMENT ON COLUMN cover_letters.s3_key  IS 'Private Blob reference for exported PDF (nullable until exported)';

-- ============================================================
-- TABLE: interview_sessions
-- ============================================================
CREATE TABLE interview_sessions (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID            NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id       UUID            REFERENCES resumes(id) ON DELETE SET NULL,
    job_id          UUID            REFERENCES jobs(id) ON DELETE SET NULL,
    questions       JSONB           NOT NULL DEFAULT '[]',
    celery_task_id  VARCHAR(255),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  interview_sessions            IS 'AI-generated interview question sessions';
COMMENT ON COLUMN interview_sessions.questions  IS 'Array of {id,question,category,difficulty,hints}';

-- ============================================================
-- INDEXES
-- ============================================================

-- resumes
CREATE INDEX idx_resumes_user_id     ON resumes(user_id);
CREATE INDEX idx_resumes_status      ON resumes(status);
CREATE INDEX idx_resumes_created_at  ON resumes(created_at DESC);

-- jobs
CREATE INDEX idx_jobs_user_id        ON jobs(user_id);
CREATE INDEX idx_jobs_created_at     ON jobs(created_at DESC);

-- ats_analyses
CREATE INDEX idx_ats_user_id         ON ats_analyses(user_id);
CREATE INDEX idx_ats_resume_id       ON ats_analyses(resume_id);
CREATE INDEX idx_ats_job_id          ON ats_analyses(job_id);
CREATE INDEX idx_ats_created_at      ON ats_analyses(created_at DESC);
CREATE INDEX idx_ats_overall_score   ON ats_analyses(overall_score);

-- cover_letters
CREATE INDEX idx_cl_user_id          ON cover_letters(user_id);
CREATE INDEX idx_cl_resume_id        ON cover_letters(resume_id);
CREATE INDEX idx_cl_created_at       ON cover_letters(created_at DESC);

-- interview_sessions
CREATE INDEX idx_is_user_id          ON interview_sessions(user_id);
CREATE INDEX idx_is_resume_id        ON interview_sessions(resume_id);
CREATE INDEX idx_is_created_at       ON interview_sessions(created_at DESC);

-- JSONB GIN indexes for fast querying of parsed data
CREATE INDEX idx_resumes_parsed_data_gin  ON resumes USING GIN (parsed_data);
CREATE INDEX idx_jobs_required_skills_gin ON jobs USING GIN (required_skills);
CREATE INDEX idx_ats_detailed_report_gin  ON ats_analyses USING GIN (detailed_report);

-- ============================================================
-- TRIGGERS: Auto-update updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trg_cover_letters_updated_at
    BEFORE UPDATE ON cover_letters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

---

## JSONB Column Schemas

### `resumes.parsed_data`
```json
{
  "name": "string",
  "email": "string",
  "phone": "string | null",
  "linkedin": "string | null",
  "github": "string | null",
  "summary": "string | null",
  "skills": ["string"],
  "education": [
    {
      "degree": "string",
      "field": "string",
      "institution": "string",
      "year": "number | null",
      "gpa": "string | null"
    }
  ],
  "experience": [
    {
      "title": "string",
      "company": "string",
      "location": "string | null",
      "start_date": "string | null",
      "end_date": "string | null",
      "duration": "string | null",
      "description": "string",
      "achievements": ["string"]
    }
  ],
  "projects": [
    {
      "name": "string",
      "description": "string",
      "technologies": ["string"],
      "url": "string | null"
    }
  ],
  "certifications": [
    {
      "name": "string",
      "issuer": "string | null",
      "year": "number | null"
    }
  ]
}
```

### `ats_analyses.detailed_report`
```json
{
  "matched_keywords": ["string"],
  "missing_keywords": ["string"],
  "missing_sections": ["string"],
  "formatting_issues": ["string"],
  "formatting_positives": ["string"],
  "skill_match_details": {
    "matched": ["string"],
    "missing": ["string"],
    "bonus": ["string"]
  },
  "experience_analysis": {
    "relevance_notes": "string",
    "years_detected": "number | null",
    "years_required": "number | null"
  },
  "recommendations": ["string"],
  "strengths": ["string"]
}
```

### `interview_sessions.questions`
```json
[
  {
    "id": "number",
    "question": "string",
    "category": "Technical | Behavioral | Situational | Culture Fit",
    "difficulty": "easy | medium | hard",
    "hints": ["string"] | null,
    "sample_answer": "string | null"
  }
]
```

---

## Redis Key Schema

| Key Pattern | Value | TTL | Purpose |
|-------------|-------|-----|---------|
| `auth:refresh:{user_id}` | `refresh_token` | 7 days | Refresh token storage |
| `cache:ats:{resume_id}` | JSON | 5 min | ATS score cache |
| `cache:dashboard:{user_id}` | JSON | 5 min | Dashboard stats cache |
| `cache:analytics:{user_id}:{days}` | JSON | 5 min | Analytics cache |
| `celery-task-meta:{task_id}` | JSON | 1 day | Celery task results (managed by Celery) |
| `rate_limit:{ip}` | counter | 1 min | SlowAPI rate limit counter |

---

## pgvector Embeddings

Vectors are stored in the Supabase `vector_embeddings` table, keyed by resume/job UUID and owner UUID. JSONB metadata stores the source type and feature metadata.

- **Model**: `all-MiniLM-L6-v2` → 384-dimensional vectors
- **Distance metric**: Cosine similarity
- **Used for**: Semantic job matching and experience relevance in ATS scoring
- **Index**: HNSW cosine index

---

## Migration Strategy

Database migrations are managed with **Alembic** (auto-generated from SQLAlchemy models).

```bash
# Generate a new migration
alembic revision --autogenerate -m "description"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current migration state
alembic current
```
