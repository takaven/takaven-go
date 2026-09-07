# Takaven Go

Takaven Go is TAKAVEN's internal evidence-led growth engine for the LeaseDesk pilot.

Current project truth: **Stage 1 PASS · Stage 2 PASS · Stage 3A PASS · Stage 3B implementation COMPLETE / deterministic verification PASS / final verdict STOP.**

Stage 1 provides Product Truth, authentication, versioning and audit controls. Stage 2 provides the full manual growth loop. Stage 3A adds the OpenAI execution boundary and trace record. Stage 3B's Generate-12 path is implemented on this PR branch and verified with mocked and integration checks. It remains STOP pending a controlled real-OpenAI generation and independent output-quality review.

Repository truth: [Product](docs/PRODUCT.md), [Architecture](docs/ARCHITECTURE.md), [Build Status](docs/BUILD_STATUS.md), [Decisions](docs/DECISIONS.md), [Benchmarks](docs/BENCHMARKS.md), [Testing](docs/TESTING.md), [Security](docs/SECURITY.md), [Limitations](docs/LIMITATIONS.md), and [Changelog](docs/CHANGELOG.md).

## Local setup

Prerequisites: Python 3.12, Node.js, npm, and a PostgreSQL database.

1. Create a PostgreSQL database and operator whose credentials are not committed here.
2. Copy `.env.example` to `.env` and replace every placeholder. Generate a random
   `SESSION_SECRET` containing at least 32 characters. Keep `COOKIE_SECURE=true` outside
   plain-HTTP local development.
3. Install and build:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements.lock
   .\.venv\Scripts\python -m pip install --no-deps -e .
   npm ci
   npm run build
   ```

4. Apply the schema and start the application:

   ```powershell
   .\.venv\Scripts\alembic upgrade head
   .\.venv\Scripts\uvicorn app.main:app --reload
   ```

5. Open `http://127.0.0.1:8000` and sign in with `OPERATOR_PASSWORD`.

The application deliberately refuses to start when required environment configuration
is absent or invalid. The first successful start seeds LeaseDesk and its canonical Truth
idempotently after the migration has created the schema.

## Verification

```powershell
.\.venv\Scripts\black --check app migrations tests
.\.venv\Scripts\ruff check .
.\.venv\Scripts\pytest --cov=app --cov-report=term-missing
npm audit
```

`requirements.lock` and `package-lock.json` contain the exact verified Python and
frontend dependency versions. Update either lock intentionally and rerun the full
verification suite; do not rely on unconstrained clean-environment resolution.

## Real PostgreSQL smoke test

Point `DATABASE_URL` at an empty, disposable PostgreSQL database whose name contains
`stage1_smoke`, set the other required environment variables, then run:

```powershell
.\.venv\Scripts\python tests\postgres_smoke.py
```

The guard is deliberate: this destructive integration test downgrades the target to
Alembic base before rebuilding it. It verifies the authenticated Truth workflow,
PostgreSQL indexes and constraints, database-level immutability, atomic approval audit,
clean downgrade/re-upgrade, and reseeding.
