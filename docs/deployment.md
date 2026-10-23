# SmartHire AI — Vercel and Supabase Deployment

The application is deployed as one Vercel project: Next.js frontend, FastAPI API, and Celery worker. Supabase provides PostgreSQL and pgvector. Upstash Redis remains the Celery broker/result store, and Vercel Blob stores uploaded PDFs and generated reports.

Vercel Services and Daemons are currently beta features. Your Vercel team must have access to them. Vercel Functions have execution and memory limits; the API is stateless, while the Celery worker runs as a daemon. See [Vercel Services](https://vercel.com/docs/services), [Vercel Daemons](https://vercel.com/daemons), and [Function limits](https://vercel.com/docs/functions/limitations).

## 1. Create the Supabase database

1. Create a Supabase project in a region close to the Vercel workload.
2. In **Project Settings → Database → Connection string**, select **Session pooler**.
3. Set the database URL in the form below. Use the project-specific username and password Supabase provides; URL-encode reserved characters in the password.

   ```text
   postgresql+asyncpg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres?ssl=require
   ```

4. Save the URL as the GitHub Actions secret `DATABASE_URL`. The deployment workflow applies Alembic migrations before deploying. Migration `002_pgvector_embeddings` enables the Supabase `vector` extension and creates storage for 384-dimensional resume and job embeddings.

The app uses its own JWT authentication. The Supabase service-role key is not required and must not be exposed to the browser.

## 2. Configure Redis and file storage

- Create a managed Redis instance reachable from Vercel. Set `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` using the provider’s TLS connection details. Celery needs Redis; this deployment does not host a Redis server on Vercel.
- Create a **private** Vercel Blob store and connect it to the project. Keep its `BLOB_READ_WRITE_TOKEN` server-side.
- Get a Google Gemini API key and keep it in `GEMINI_API_KEY`.

## 3. Configure the Vercel project

1. Import the repository into Vercel with the **repository root** as the project root (not `frontend/`).
2. Set the project framework to **Services** and confirm your team can use both Services and Daemons.
3. The root `vercel.json` routes `/api/*` to FastAPI and other paths to Next.js. It also defines a Celery daemon using `backend/Dockerfile.vercel`.
4. Add these server-side environment variables for Production and Preview:

   | Variable | Value |
   |---|---|
   | `APP_ENV` | `production` |
   | `SECRET_KEY` | A random secret of at least 32 characters |
   | `DATABASE_URL` | Supabase Session Pooler URL above |
   | `DB_POOL_SIZE` | `2` |
   | `DB_MAX_OVERFLOW` | `0` |
   | `REDIS_URL` | Managed Redis TLS URL |
   | `CELERY_BROKER_URL` | Redis broker URL |
   | `CELERY_RESULT_BACKEND` | Redis result backend URL |
   | `BLOB_READ_WRITE_TOKEN` | Private Vercel Blob token |
   | `GEMINI_API_KEY` | Google AI Studio key |
   | `ALLOWED_ORIGINS` | Your Vercel production origin, e.g. `https://smarthire-ai.vercel.app` |

   The frontend calls `/api/v1` on the same Vercel domain. Do not set the database URL or any secret under a `NEXT_PUBLIC_` variable.

5. Choose a region for the Celery daemon in `vercel.json` (`iad1` is the current default) and use a nearby Supabase/Redis region where possible.
6. Deploy. The first deploy can only succeed after the project enables the beta features and all required variables are configured.

## 4. Configure GitHub Actions deployment

The workflow runs migrations first and then deploys the full project through the Vercel CLI. Add these repository or `production` environment secrets:

| Secret | Purpose |
|---|---|
| `DATABASE_URL` | Supabase migration connection |
| `SECRET_KEY` | Settings validation during migration |
| `VERCEL_TOKEN` | Vercel deployment token |
| `VERCEL_ORG_ID` | Vercel team/account ID |
| `VERCEL_PROJECT_ID` | Vercel project ID |

If Vercel Git integration is also configured to build every push, disable one of the two automatic deploy paths to avoid duplicate deployments. The GitHub workflow is set up to apply database migrations before deployment.

## 5. First migration and verification

Run the deployment workflow manually or push the configured branch. It applies `alembic upgrade head` before deploying. Then verify:

- `https://<your-domain>/api/health` reports the database and Redis as connected.
- `https://<your-domain>/api/docs` loads FastAPI Swagger docs.
- The frontend loads from the same domain and can register, log in, upload a resume, and poll the Celery task status.
- Vercel Logs show the Celery daemon running and consuming tasks.

The repository's current local environment still points at the existing Neon database. No database or file data has been copied to Supabase or Vercel Blob. Before switching production traffic, export and import the PostgreSQL data from Neon, migrate any stored files into the private Blob store, and update the API/worker `DATABASE_URL`. ChromaDB-only vectors are regenerated from resume/job text when first requested; the database records and file objects require their own migration.

## Troubleshooting

- **Services config ignored:** confirm the Vercel project root is the repository root and the project framework is set to Services.
- **Daemon unavailable:** ask the Vercel team owner to enable Daemons beta access; inspect the daemon logs and Redis connectivity.
- **Database connection error:** check the Session Pooler host, password URL encoding, port 5432, and TLS query parameter.
- **Migration fails on `vector`:** enable the Supabase `vector` extension for the project and rerun the workflow.
- **Function timeout or memory error:** the SentenceTransformers model and PDF/AI workloads are memory-intensive. Review Vercel function limits and logs; the Celery daemon handles the longer asynchronous jobs.
