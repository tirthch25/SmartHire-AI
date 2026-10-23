# SmartHire AI — API Documentation

**Base URL (Production):** `https://<your-vercel-domain>/api/v1`
**Base URL (Local):** `http://localhost:8000/api/v1`  
**OpenAPI Interactive Docs:** `https://<your-vercel-domain>/api/docs` (Swagger UI)
**Local Swagger UI:** `http://localhost:8000/api/docs`
**ReDoc:** `https://<your-vercel-domain>/api/redoc` or `http://localhost:8000/api/redoc`

---

## Authentication

All protected endpoints require a `Bearer` token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens expire in **15 minutes**. Use `POST /auth/refresh` to get a new access token.

---

## Error Response Format

All errors return a consistent JSON structure:

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| HTTP Status | Meaning |
|-------------|---------|
| `400` | Bad Request — invalid input |
| `401` | Unauthorized — missing or invalid token |
| `403` | Forbidden — insufficient permissions |
| `404` | Not Found |
| `409` | Conflict — e.g. duplicate email |
| `413` | Payload Too Large — file exceeds 10 MB |
| `422` | Unprocessable Entity — Pydantic validation error |
| `429` | Too Many Requests — rate limit exceeded |
| `500` | Internal Server Error |

---

## Rate Limits

| Endpoint Group | Limit |
|----------------|-------|
| `POST /auth/*` | 10 requests / minute |
| `POST /resume/upload` | 5 requests / minute |
| All other endpoints | 60 requests / minute |

---

## Endpoints

---

### `/auth` — Authentication

#### `POST /auth/register`
Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "Jane Doe"
}
```

**Constraints:** `password` min 8 chars, must contain uppercase, lowercase, digit.

**Response `201`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

#### `POST /auth/login`
Authenticate and receive JWT tokens.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

#### `POST /auth/refresh`
Get a new access token using a refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response `200`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

#### `POST /auth/logout`
🔒 **Auth Required**  
Invalidate the current refresh token.

**Response `200`:**
```json
{ "message": "Logged out successfully" }
```

---

#### `GET /auth/me`
🔒 **Auth Required**  
Get current user profile.

**Response `200`:**
```json
{
  "id": "550e8400-...",
  "email": "user@example.com",
  "full_name": "Jane Doe",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### `/resume` — Resume Management

#### `POST /resume/upload`
🔒 **Auth Required** | Rate: 5/min  
Upload a PDF resume. Triggers background processing via Celery.

**Request:** `multipart/form-data`
| Field | Type | Description |
|-------|------|-------------|
| `file` | `File` | PDF file (max 10 MB) |

**Response `202`:**
```json
{
  "resume_id": "abc123...",
  "task_id": "celery-task-uuid",
  "status": "pending",
  "message": "Resume uploaded. Processing started."
}
```

---

#### `GET /resume/{resume_id}`
🔒 **Auth Required**  
Get resume metadata and parsed entities.

**Response `200`:**
```json
{
  "id": "abc123...",
  "filename": "jane_doe_resume.pdf",
  "file_size": 204800,
  "status": "completed",
  "parsed_data": {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "phone": "+1-555-0100",
    "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "education": [
      {
        "degree": "B.S. Computer Science",
        "institution": "MIT",
        "year": 2020
      }
    ],
    "experience": [
      {
        "title": "Backend Engineer",
        "company": "TechCorp",
        "duration": "2020-2023",
        "description": "Built scalable APIs..."
      }
    ],
    "projects": [
      {
        "name": "ResumeBot",
        "description": "AI-powered resume parser",
        "technologies": ["Python", "NLP"]
      }
    ],
    "certifications": ["AWS Solutions Architect", "Google Cloud Professional"]
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

#### `GET /resume/list`
🔒 **Auth Required**  
List all resumes for the current user (paginated).

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `page_size` | int | 10 | Items per page (max 50) |

**Response `200`:**
```json
{
  "items": [ /* array of resume summaries */ ],
  "total": 5,
  "page": 1,
  "page_size": 10
}
```

---

#### `DELETE /resume/{resume_id}`
🔒 **Auth Required**  
Delete a resume and its private Blob file.

**Response `204`:** No content.

---

#### `GET /resume/{resume_id}/download`
🔒 **Auth Required**  
Get an authenticated API route to download the original PDF.

**Response `200`:**
```json
{
  "download_url": "https://s3.amazonaws.com/smarthire-ai/resumes/...",
  "expires_in": 3600
}
```

---

### `/ats` — ATS Scoring

#### `POST /ats/analyze`
🔒 **Auth Required**  
Trigger ATS analysis for a resume against a job description. Returns a task_id for polling.

**Request Body:**
```json
{
  "resume_id": "abc123...",
  "job_id": "def456..."
}
```

**Response `202`:**
```json
{
  "analysis_id": "ghi789...",
  "task_id": "celery-task-uuid",
  "status": "pending"
}
```

---

#### `GET /ats/status/{task_id}`
🔒 **Auth Required**  
Poll Celery task status.

**Response `200`:**
```json
{
  "task_id": "celery-task-uuid",
  "state": "PROGRESS",
  "progress": 65,
  "message": "Computing skills match score..."
}
```

States: `PENDING` | `PROGRESS` | `SUCCESS` | `FAILURE`

---

#### `GET /ats/score/{resume_id}`
🔒 **Auth Required**  
Get the latest completed ATS analysis for a resume.

**Response `200`:**
```json
{
  "id": "ghi789...",
  "resume_id": "abc123...",
  "job_id": "def456...",
  "overall_score": 78.5,
  "components": {
    "keyword_match": { "score": 82.0, "weight": 0.30, "weighted": 24.6 },
    "formatting":    { "score": 90.0, "weight": 0.15, "weighted": 13.5 },
    "section_completeness": { "score": 85.0, "weight": 0.15, "weighted": 12.75 },
    "skills_match":  { "score": 71.0, "weight": 0.20, "weighted": 14.2 },
    "experience_relevance": { "score": 68.5, "weight": 0.20, "weighted": 13.7 }
  },
  "detailed_report": {
    "matched_keywords": ["Python", "FastAPI", "REST API"],
    "missing_keywords": ["Kubernetes", "Terraform"],
    "missing_sections": [],
    "formatting_issues": ["Consider using more bullet points"],
    "recommendations": ["Add quantified achievements to experience section"]
  },
  "created_at": "2024-01-15T10:35:00Z"
}
```

---

#### `GET /ats/history`
🔒 **Auth Required**  
List all ATS analyses for the current user (paginated).

**Query Parameters:** `page`, `page_size`, `resume_id` (optional filter)

---

#### `GET /ats/export/{analysis_id}`
🔒 **Auth Required**  
Export ATS analysis as a PDF report. Triggers PDF generation if not already done.

**Response `200`:**
```json
{
  "download_url": "https://s3.amazonaws.com/smarthire-ai/reports/...",
  "expires_in": 3600
}
```

---

### `/job` — Job Description Management

#### `POST /job/create`
🔒 **Auth Required**  
Create and save a job description.

**Request Body:**
```json
{
  "title": "Senior Backend Engineer",
  "company": "Acme Corp",
  "description": "We are looking for a Python expert..."
}
```

**Response `201`:**
```json
{
  "id": "def456...",
  "title": "Senior Backend Engineer",
  "company": "Acme Corp",
  "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
  "parsed_data": { /* Gemini-extracted job requirements */ },
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

#### `GET /job/list`
🔒 **Auth Required**  
List user's saved job descriptions.

---

#### `DELETE /job/{job_id}`
🔒 **Auth Required**  
Delete a saved job description.

---

#### `POST /job/match`
🔒 **Auth Required**  
Get semantic similarity score between a resume and job description.

**Request Body:**
```json
{
  "resume_id": "abc123...",
  "job_id": "def456..."
}
```

**Response `200`:**
```json
{
  "overall_match_score": 74.2,
  "skills_overlap": 0.71,
  "experience_similarity": 0.68,
  "education_match": true,
  "matched_skills": ["Python", "FastAPI", "PostgreSQL"],
  "missing_skills": ["Kubernetes", "Terraform", "Go"],
  "bonus_skills": ["Machine Learning", "PostgreSQL"]
}
```

---

#### `GET /job/skill-gap`
🔒 **Auth Required**  
Get detailed skill gap analysis with learning recommendations.

**Query Parameters:** `resume_id`, `job_id`

**Response `200`:**
```json
{
  "resume_id": "abc123...",
  "job_id": "def456...",
  "matched_skills": ["Python", "FastAPI"],
  "missing_skills": [
    {
      "skill": "Kubernetes",
      "importance": "high",
      "learning_resources": [
        { "title": "Kubernetes Official Docs", "url": "https://kubernetes.io/docs" },
        { "title": "KodeKloud K8s Course", "url": "https://kodekloud.com" }
      ]
    }
  ],
  "bonus_skills": ["Machine Learning"],
  "gap_score": 35.0,
  "recommendations": ["Focus on container orchestration (Kubernetes)", "Learn Infrastructure as Code (Terraform)"]
}
```

---

### `/interview` — Interview Question Generation

#### `POST /interview/generate`
🔒 **Auth Required**  
Generate interview questions. Dispatches Celery task.

**Request Body:**
```json
{
  "resume_id": "abc123...",
  "job_id": "def456...",
  "focus_areas": ["system design", "behavioral"],
  "difficulty": "medium",
  "question_count": 15
}
```

**Response `202`:**
```json
{
  "session_id": "jkl012...",
  "task_id": "celery-task-uuid",
  "status": "pending"
}
```

---

#### `GET /interview/status/{task_id}`
🔒 **Auth Required**  
Poll Celery task status.

---

#### `GET /interview/{session_id}`
🔒 **Auth Required**  
Get generated interview questions.

**Response `200`:**
```json
{
  "session_id": "jkl012...",
  "resume_id": "abc123...",
  "job_id": "def456...",
  "questions": [
    {
      "id": 1,
      "question": "Describe a time you optimized a slow database query.",
      "category": "Technical",
      "difficulty": "medium",
      "hints": ["Think about indexing", "Consider query execution plans"]
    },
    {
      "id": 2,
      "question": "How do you handle disagreements with teammates?",
      "category": "Behavioral",
      "difficulty": "easy",
      "hints": null
    }
  ],
  "created_at": "2024-01-15T10:40:00Z"
}
```

---

#### `GET /interview/list`
🔒 **Auth Required**  
List all interview sessions for the current user.

---

### `/cover-letter` — Cover Letter Generation

#### `POST /cover-letter/generate`
🔒 **Auth Required**  
Generate a personalized cover letter. Dispatches Celery task.

**Request Body:**
```json
{
  "resume_id": "abc123...",
  "job_id": "def456...",
  "tone": "professional",
  "highlights": ["leadership experience", "open source contributions"],
  "word_limit": 400
}
```

`tone` options: `professional` | `confident` | `enthusiastic` | `formal`

**Response `202`:**
```json
{
  "letter_id": "mno345...",
  "task_id": "celery-task-uuid",
  "status": "pending"
}
```

---

#### `GET /cover-letter/status/{task_id}`
🔒 **Auth Required**  
Poll Celery task status.

---

#### `GET /cover-letter/{letter_id}`
🔒 **Auth Required**  
Get generated cover letter.

**Response `200`:**
```json
{
  "id": "mno345...",
  "resume_id": "abc123...",
  "job_id": "def456...",
  "tone": "professional",
  "content": "Dear Hiring Manager,\n\nI am excited to apply...",
  "word_count": 387,
  "created_at": "2024-01-15T10:45:00Z",
  "updated_at": "2024-01-15T10:45:00Z"
}
```

---

#### `PUT /cover-letter/{letter_id}`
🔒 **Auth Required**  
Update/edit a cover letter.

**Request Body:**
```json
{
  "content": "Updated cover letter content..."
}
```

---

#### `GET /cover-letter/list`
🔒 **Auth Required**  
List all cover letters for the current user.

---

#### `GET /cover-letter/{letter_id}/export`
🔒 **Auth Required**  
Export cover letter as PDF (authenticated private download).

**Response `200`:**
```json
{
  "download_url": "https://s3.amazonaws.com/smarthire-ai/cover-letters/...",
  "expires_in": 3600
}
```

---

### `/dashboard` — Analytics & Dashboard

#### `GET /dashboard/stats`
🔒 **Auth Required** | Redis-cached (5 min)  
Get summary statistics for the current user.

**Response `200`:**
```json
{
  "total_resumes": 5,
  "total_analyses": 12,
  "total_jobs": 8,
  "total_cover_letters": 4,
  "average_ats_score": 74.3,
  "best_ats_score": 89.0,
  "last_upload": "2024-01-15T10:30:00Z"
}
```

---

#### `GET /dashboard/analytics`
🔒 **Auth Required** | Redis-cached (5 min)  
Get score trends and analytics data for charts.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `days` | int | 30 | Number of days to look back |

**Response `200`:**
```json
{
  "score_trend": [
    { "date": "2024-01-10", "score": 65.0 },
    { "date": "2024-01-12", "score": 71.5 },
    { "date": "2024-01-15", "score": 78.5 }
  ],
  "component_averages": {
    "keyword_match": 79.2,
    "formatting": 88.0,
    "section_completeness": 85.0,
    "skills_match": 68.5,
    "experience_relevance": 71.3
  },
  "top_matched_jobs": [
    { "job_title": "Senior Backend Engineer", "company": "Acme", "score": 89.0 }
  ]
}
```

---

#### `GET /dashboard/activity`
🔒 **Auth Required**  
Get recent user activity feed.

**Response `200`:**
```json
{
  "activities": [
    {
      "type": "resume_uploaded",
      "description": "Uploaded jane_doe_resume.pdf",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "type": "ats_analysis_completed",
      "description": "ATS score: 78.5 for Senior Backend Engineer at Acme Corp",
      "timestamp": "2024-01-15T10:35:00Z"
    }
  ]
}
```
