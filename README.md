# AI Invoice Processing SaaS

AI-powered invoice processing for Slovak SMBs: upload PDF invoices, extract structured fields, validate them, review in the UI, and export as Pohoda XML, CSV, JSON, or webhook payload.

## Portfolio summary

This project demonstrates a practical AI SaaS architecture: a typed FastAPI backend, a Next.js review interface, Supabase persistence/storage, deterministic fallback parsing for reliable tests, and export formats that match real accounting workflows.

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

Notable backend vars:

- `LOCAL_LLM_URL` / `LOCAL_LLM_MODEL` — OpenAI-compatible local LLM (e.g. LM Studio at
  `http://localhost:1234/v1`). Takes priority; falls back to `GEMINI_API_KEY`, then to the
  deterministic parser when neither is set.
- `CORS_ORIGINS` — comma-separated allowed origins, or `*` for any (local dev only).
  Restrict this in production.
- `ENABLE_AUTH` — `true` to require a verified Clerk session JWT on tenant-scoped
  endpoints. When `false` (default), the app runs as a single `"default"` tenant with no
  token required (local dev).
- `CLERK_JWKS_URL` / `CLERK_ISSUER` — Clerk JWKS endpoint and (optional) issuer used to
  verify session tokens when `ENABLE_AUTH=true`.

## Multi-tenant config & auth

Each client's config (required fields, validation rules, output connector, confidence
threshold) is one row in `client_configs`, keyed by client id.

The tenant is resolved **server-side from a verified Clerk session JWT** (the `org_id`/`sub`
claim) — never from a client-supplied header. With `ENABLE_AUTH=false` everything runs as
the single `"default"` tenant. With `ENABLE_AUTH=true`, tenant-scoped endpoints
(`/api/config`, `/api/invoices/*`, `/api/export/*`, `/api/vendors/*`, `/api/stats`) require a
`Bearer` token; the web app attaches it automatically (client components via Clerk
`getToken()`, server components via `auth().getToken()`).

**Data isolation:** invoices, vendors, config, and stats are all scoped by `client_id`. Every
read and write filters on the verified tenant key, so one tenant cannot see or mutate
another's data (see `test_invoice_data_isolated_per_tenant` / `test_vendor_data_isolated_per_tenant`).
The DB tables are also locked to the `service_role` (RLS, browser has no direct access).

**Remaining gaps:** `processing_logs` has no `client_id`, so the `agent_performance` stat
(average step durations — no tenant data) is computed globally. The legacy `clients` table is
unused (config lives in `client_configs`).

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
