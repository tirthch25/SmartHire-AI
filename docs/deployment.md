# SmartHire AI — Production Deployment Guide

> **Stack**: Frontend → Vercel | Backend → Render | DB → Neon | Redis → Upstash

---

## Prerequisites

- GitHub repository pushed to `main` branch
- Accounts on: [Vercel](https://vercel.com), [Render](https://render.com), [Neon](https://neon.tech), [Upstash](https://upstash.com), [AWS](https://aws.amazon.com) (for S3), [Google AI Studio](https://aistudio.google.com) (for Gemini)

---

## Step 1 — Neon PostgreSQL (Database)

1. Go to [neon.tech](https://neon.tech) → **New Project**
2. Name it `smarthire-ai`, region: **US East (AWS)** or closest to your users
3. After creation, go to **Connection Details** → copy the **Connection string**
4. It will look like:
   ```
   postgresql://user:password@ep-xxx-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
5. **Convert for asyncpg** (replace `postgresql://` with `postgresql+asyncpg://`):
   ```
   postgresql+asyncpg://user:password@ep-xxx-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
6. Save this as your `DATABASE_URL` — you'll need it in Steps 3 and 5.

---

## Step 2 — Upstash Redis (Cache + Celery Broker)

1. Go to [upstash.com](https://upstash.com) → **Create Database**
2. Name: `smarthire-redis`, Type: **Regional**, Region: **US-East-1**
3. After creation, go to **Details** → copy the **Redis URL** (TLS version):
   ```
   rediss://:your_password@your-endpoint.upstash.io:6379
   ```
4. You'll use this URL for three env vars (with different DB indices):
   - `REDIS_URL` → `rediss://:pass@host:port`
   - `CELERY_BROKER_URL` → `rediss://:pass@host:port/1`
   - `CELERY_RESULT_BACKEND` → `rediss://:pass@host:port/2`

---

## Step 3 — Cloudflare R2 (Free File Storage)

> **Why R2?** Free tier: **10 GB storage**, **1M writes/month**, **10M reads/month**, and **zero egress fees** (AWS charges ~$0.09/GB for egress). Fully S3-compatible — no code changes needed.

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → create a free account if needed
2. In the left sidebar → **R2 Object Storage** → **Create bucket**
3. Bucket name: `smarthire-ai`, Location: **Automatic**
4. Note your **Account ID** from the Cloudflare dashboard right sidebar

### Create R2 API Token

5. Go to **R2** → **Manage R2 API Tokens** → **Create API Token**
6. Set permissions: **Object Read & Write** → scope to your `smarthire-ai` bucket
7. Click **Create API Token** → copy and save:
   - **Access Key ID** → save as `AWS_ACCESS_KEY_ID`
   - **Secret Access Key** → save as `AWS_SECRET_ACCESS_KEY`
8. Your endpoint URL: `https://<YOUR_ACCOUNT_ID>.r2.cloudflarestorage.com` → save as `STORAGE_ENDPOINT_URL`

> **Note**: Despite the `AWS_` prefix, these are Cloudflare R2 credentials. boto3 uses these names internally but routes to R2 via the `STORAGE_ENDPOINT_URL`.

---

## Step 4 — Google Gemini API Key

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API Key** → select or create a project
3. Copy the key → save as `GEMINI_API_KEY`

---

## Step 5 — Render Backend Deployment

### 5.1 — Connect Repository

1. Go to [render.com](https://render.com) → **New** → **Blueprint**
2. Connect your GitHub account and select `SmartHire-AI` repo
3. Render will detect `render.yaml` automatically and show two services:
   - `smarthire-api` (Web Service)
   - `smarthire-celery` (Background Worker)
4. Click **Apply**

### 5.2 — Set Environment Variables

After the services are created, go to each service → **Environment** and fill in all `sync: false` variables:

#### For `smarthire-api`:

| Variable | Value |
|---|---|
| `SECRET_KEY` | Generate: `openssl rand -hex 32` |
| `DATABASE_URL` | Your Neon asyncpg URL from Step 1 |
| `REDIS_URL` | Your Upstash Redis URL from Step 2 |
| `CELERY_BROKER_URL` | Upstash URL + `/1` |
| `CELERY_RESULT_BACKEND` | Upstash URL + `/2` |
| `ALLOWED_ORIGINS` | `https://your-app.vercel.app` (update after Vercel deploy) |
| `STORAGE_ENDPOINT_URL` | `https://<account_id>.r2.cloudflarestorage.com` (from Step 3) |
| `AWS_ACCESS_KEY_ID` | R2 Access Key ID from Step 3 |
| `AWS_SECRET_ACCESS_KEY` | R2 Secret Access Key from Step 3 |
| `AWS_S3_BUCKET_NAME` | `smarthire-ai` |
| `GEMINI_API_KEY` | From Step 4 |

#### For `smarthire-celery`:

Copy the same secrets: `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `STORAGE_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME`, `GEMINI_API_KEY`

### 5.3 — Run Database Migrations

Once the API service is running, open the Render **Shell** tab for `smarthire-api` and run:

```bash
alembic upgrade head
```

> **Alternatively**, migrations also run automatically via GitHub Actions on every push to `main` (see `deploy-backend.yml`).

### 5.4 — Note your Render URL

Your API will be available at: `https://smarthire-api.onrender.com`
Verify: `https://smarthire-api.onrender.com/health`

---

## Step 6 — Vercel Frontend Deployment

### 6.1 — Import Project

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import from GitHub → select `SmartHire-AI`
3. **Root Directory**: set to `frontend`
4. Framework: **Next.js** (auto-detected)
5. Build command: `npm run build` (auto from `vercel.json`)

### 6.2 — Set Environment Variables

In Vercel → Project → **Settings** → **Environment Variables**:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://smarthire-api.onrender.com/api/v1` |
| `NEXT_PUBLIC_APP_NAME` | `SmartHire AI` |

> Set these for **Production**, **Preview**, and **Development** environments.

### 6.3 — Deploy

Click **Deploy**. Vercel will build and deploy the Next.js app.

Your frontend URL: `https://smarthire-ai.vercel.app` (or your custom domain)

### 6.4 — Update CORS in Render

Go back to Render → `smarthire-api` → Environment:
- Update `ALLOWED_ORIGINS` to your actual Vercel URL:
  ```
  https://smarthire-ai.vercel.app
  ```
- Click **Save Changes** → service auto-restarts

---

## Step 7 — GitHub Actions Secrets (CI/CD)

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add all of the following:

### Backend Secrets (for `deploy-backend.yml`)

| Secret Name | Description |
|---|---|
| `DATABASE_URL` | Neon asyncpg URL |
| `SECRET_KEY` | 32-char hex secret |
| `RENDER_DEPLOY_HOOK_URL` | Render → Service → Settings → Deploy Hook URL |

### Frontend Secrets (for `deploy-frontend.yml`)

| Secret Name | Description |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://smarthire-api.onrender.com/api/v1` |
| `VERCEL_TOKEN` | Vercel → Account Settings → Tokens → Create |
| `VERCEL_ORG_ID` | Vercel → Account Settings → General → Team ID |
| `VERCEL_PROJECT_ID` | Vercel → Project → Settings → General → Project ID |

### Optional (CI tests)

| Secret Name | Description |
|---|---|
| `GEMINI_API_KEY` | For running integration tests in CI |
| `AWS_ACCESS_KEY_ID` | For S3 mocks in CI |
| `AWS_SECRET_ACCESS_KEY` | For S3 mocks in CI |

---

## Step 8 — Post-Deploy Verification

Run through this checklist after deployment:

### Backend

- [ ] `GET https://smarthire-api.onrender.com/health` returns `{"status": "healthy"}`
- [ ] `GET https://smarthire-api.onrender.com/docs` shows Swagger UI
- [ ] `GET https://smarthire-api.onrender.com/` returns JSON with app name
- [ ] `services.database` = `"connected"` in health response
- [ ] `services.redis` = `"connected"` in health response

### Frontend

- [ ] Vercel URL loads without errors
- [ ] No CORS errors in browser console
- [ ] Can register a new user
- [ ] Can log in and reach the dashboard

### CI/CD

- [ ] Push to `main` triggers `deploy-backend.yml` and `deploy-frontend.yml`
- [ ] Alembic migrations run successfully in CI
- [ ] Vercel deployment succeeds

---

## Troubleshooting

### CORS errors in browser
→ Ensure `ALLOWED_ORIGINS` in Render exactly matches your Vercel URL (no trailing slash)

### Render service keeps restarting
→ Check Render logs. Most common cause: missing env var causing crash on startup
→ Run `GET /health` and check `services` block for which service is down

### Alembic migration fails in CI
→ Check `DATABASE_URL` GitHub secret is set and uses `postgresql+asyncpg://` scheme
→ Neon requires `?sslmode=require` at the end of the URL

### Vercel build fails
→ Check that `NEXT_PUBLIC_API_URL` is set in Vercel environment variables
→ Verify `frontend/` is set as the root directory in Vercel project settings

### ChromaDB data lost on redeploy (expected on free tier)
→ Vector embeddings are regenerated automatically on next use
→ To persist: upgrade Render to Starter plan ($7/mo) and add a disk mounted at `/chroma/data`
