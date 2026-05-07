# AI Invoice Processing SaaS

AI-powered invoice processing for Slovak SMBs: upload PDF invoices, extract structured fields, validate them, review in the UI, and export as Pohoda XML, CSV, JSON, or webhook payload.

## Stack

- **Frontend:** Next.js + TypeScript + Tailwind CSS, deployed on Vercel
- **Backend:** FastAPI + Pydantic, deployable as a container
- **Database/storage:** Supabase Postgres + pgvector + Storage
- **AI pipeline:** LangGraph-ready service boundaries with deterministic MVP fallback
- **CI/CD:** GitHub Actions for backend tests and frontend checks

## Monorepo layout

```txt
apps/
  api/      FastAPI backend
  web/      Next.js frontend
supabase/
  migrations/ SQL schema for Supabase
.github/
  workflows/ CI
```

## Local development

### 1. Backend

```bash
cd apps/api
uv sync --extra dev
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
```

Run tests:

```bash
cd apps/api
uv run pytest -q
```

### 2. Frontend

```bash
cd apps/web
npm install
cp .env.example .env.local
npm run dev
```

Run checks:

```bash
npm run lint
npm run typecheck
npm test
```

### 3. Supabase

Create a Supabase project, then run `supabase/migrations/0001_initial.sql` in the SQL editor or with the Supabase CLI.

Required buckets:

- `invoice-files` for uploaded PDF files

## Environment variables

Backend: `apps/api/.env.example`
Frontend: `apps/web/.env.example`

## CI/CD

GitHub Actions runs on every push and pull request:

- backend: `uv run pytest -q`
- frontend: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`

Vercel deployment:

1. Import this GitHub repo in Vercel.
2. Set **Root Directory** to `apps/web`.
3. Add frontend env vars from `apps/web/.env.example`.
4. Set `NEXT_PUBLIC_API_URL` to your deployed FastAPI API URL.

## Supabase notes

This MVP uses Supabase for Postgres, pgvector, and file storage. The original spec mentioned Azure Blob Storage and Azure deployment; those can be added later without changing the public app flow.

## Current MVP behavior

- Upload endpoint accepts PDFs and stores an invoice record.
- Pipeline has typed Extract → Validate → Enrich → Format stages.
- Deterministic parser handles common invoice text patterns for tests/local demo.
- Low-confidence or invalid fields are flagged for manual review.
- JSON/CSV/Pohoda XML formatting is covered by tests.
