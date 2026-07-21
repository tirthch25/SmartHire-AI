# Contributing to SmartHire AI

Thank you for your interest in contributing! This document covers the development workflow, code standards, and submission process.

---

## Development Setup

1. **Fork** the repository on GitHub
2. **Clone** your fork: `git clone https://github.com/YOUR-USERNAME/SmartHire-AI.git`
3. Follow the **Local Development** steps in [README.md](README.md)
4. Create a **feature branch**: `git checkout -b feat/your-feature-name`

---

## Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/<name>` | `feat/skill-gap-chart` |
| Bug fix | `fix/<name>` | `fix/ats-score-rounding` |
| Documentation | `docs/<name>` | `docs/api-examples` |
| Refactor | `refactor/<name>` | `refactor/celery-tasks` |
| Test | `test/<name>` | `test/cover-letter-export` |

---

## Code Standards

### Backend (Python)

- **Style**: Follow [PEP 8](https://peps.python.org/pep-0008/)
- **Linting**: `ruff check app/` (must pass before PR)
- **Type hints**: Required on all public functions
- **Docstrings**: Required on all modules, classes, and public methods
- **Tests**: Required for all new API endpoints (see `tests/backend/`)
- **Async**: Use `async/await` everywhere in FastAPI routes; Celery tasks use sync DB sessions

```python
# Good
async def get_resume(
    resume_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """Retrieve a resume by ID, scoped to the current user."""
    resume = await _get_resume_or_404(db, str(resume_id), user_id)
    return ResumeResponse.model_validate(resume)
```

### Frontend (TypeScript)

- **Style**: Follow the existing component patterns in `src/components/`
- **Types**: Prefer explicit interfaces over `any`
- **CSS**: Use CSS variables from `globals.css` — avoid inline colors
- **API calls**: Use the `api` client from `src/lib/api.ts`

---

## Writing Tests

All new API endpoints **must** have tests. Place them in `tests/backend/test_<feature>.py`.

```python
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

class TestMyFeature:
    async def test_success(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/my-endpoint", json={...}, headers=auth_headers)
        assert resp.status_code == 201
        # assert specific fields in resp.json()

    async def test_unauthenticated(self, client: AsyncClient):
        resp = await client.post("/api/v1/my-endpoint", json={...})
        assert resp.status_code == 401
```

Run tests with:
```bash
pytest tests/backend/test_<feature>.py -v
```

---

## Pull Request Process

1. **Ensure CI passes**: `pytest` + `ruff check` + `npm run build`
2. **Add/update tests** for any changed behavior
3. **Update docs** if you change API contracts or add new environment variables
4. **Keep PRs focused**: one feature or fix per PR
5. **Write a clear PR description** explaining:
   - What the change does
   - Why it's needed
   - Any trade-offs or alternatives considered

### PR Checklist

- [ ] Tests added/updated and passing locally
- [ ] Ruff linter passes (`ruff check backend/app/`)
- [ ] Frontend builds (`npm run build`)
- [ ] No secrets or credentials committed
- [ ] Docstrings added for new public functions
- [ ] `.env.example` updated if new env vars added

---

## Adding a New AI Service

1. Create `backend/app/services/my_service.py` following the existing pattern
2. Add a corresponding Celery task in `backend/app/workers/tasks.py`
3. Add API endpoint in the appropriate router under `backend/app/api/v1/`
4. Add tests in `tests/backend/test_<feature>.py`
5. Add the frontend page/component if needed

---

## Reporting Issues

Use GitHub Issues with the following templates:

- **Bug report**: Include steps to reproduce, expected vs actual behavior, and relevant log output
- **Feature request**: Describe the use case, proposed solution, and any alternatives

---

## Questions

Open a GitHub Discussion for questions that aren't bugs or feature requests.
