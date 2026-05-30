PAGES 10

--- PAGE 1 ---
AI Invoice Processing App — AGENTS.md
Project Overview
An AI-powered invoice processing SaaS app that extracts, validates, enriches, and exports
structured data from invoice PDFs. Built for small-to-medium businesses (primarily in
Slovakia) who currently process invoices manually.
Target user: Accountant processing 50–500 invoices/month, manually entering data into
Pohoda or similar accounting software.
Core value prop: Upload any invoice PDF → AI extracts all fields → review & approve →
export directly to Pohoda / CSV / JSON / Webhook. Zero manual typing.
Market gap: Hypatos and SAP target enterprises (€18,000+/year). This solves the same
problem for SMBs at €49–199/month.
Tech Stack
Layer
Technology
Frontend
Next.js + TypeScript + Tailwind CSS
Backend
FastAPI (Python)
AI Pipeline
LangGraph (multi-agent orchestration)
LLM
Azure OpenAI (GPT-4o)
Database
PostgreSQL + pgvector
File Storage
Azure Blob Storage (PDF files)
Deployment
Docker + Azure (Debian VM or Container Apps)
Export
Pohoda XML, CSV, JSON, Webhook

--- PAGE 2 ---
Architecture
Request Flow
User uploads PDF
    → Next.js frontend
    → FastAPI POST /api/invoices/upload
    → LangGraph pipeline triggered
        → Extract Agent   (fields from PDF)
        → Validate Agent  (format checks, flag issues)
        → Enrich Agent    (vendor RAG lookup, dedup check)
        → Format Agent    (output for selected connector)
    → Results saved to PostgreSQL + pgvector
    → Frontend shows review screen
    → User approves → export triggered
LangGraph Pipeline — Agent Details
State Object (shared across all agents)
class InvoiceState(TypedDict):
    invoice_id: str
    client_id: str
    raw_text: str
    extracted: dict          # output of Extract agent
    validation: dict         # output of Validate agent
    enriched: dict           # output of Enrich agent
    formatted: dict          # output of Format agent
    errors: list[str]
    config: dict             # client config loaded at start
Agent 1 — Extract
Input: raw PDF text (via PyMuPDF) + client config Task: prompt LLM to extract all invoice
fields as structured JSON Output: extracted fields with confidence scores
Fields to extract (configurable per client):
vendor_name, vendor_vat, vendor_iban
invoice_number, invoice_date, due_date

--- PAGE 3 ---
line_items (list: description, qty, unit_price, vat_rate, total)
subtotal, vat_amount, total_amount, currency
po_number (optional), cost_center (optional)
Use Pydantic structured output with confidence score (0.0–1.0) per field. Use Azure
Document Intelligence as fallback for scanned/image PDFs.
Agent 2 — Validate
Input: extracted fields + client config (validation rules) Task: check required fields, validate
formats, flag math errors Output: validation report with list of issues (severity:
error/warning)
Checks:
Required fields present (per client config)
Slovak VAT format: SK[0-9]{10}
Date format matches client config (DD.MM.YYYY for SK)
VAT math: subtotal * vat_rate ≈ vat_amount (within 0.01 tolerance)
Invoice number format (regex from config)
Currency is in allowed list
Agent 3 — Enrich
Input: validated fields + pgvector connection Task: match vendor in knowledge base,
detect duplicates, assign categories Output: enriched data with vendor metadata and
category
Steps:
1. Generate embedding of vendor name + VAT number
2. pgvector similarity search in vendors table (cosine, threshold 0.85)
3. If match found → pull stored vendor metadata (IBAN, address, category)
4. Check for duplicate: same invoice_number + vendor_vat in last 90 days
5. Assign cost_center based on vendor category if not in extracted data
Agent 4 — Format

--- PAGE 4 ---
Input: enriched data + client config (output connector type) Task: format data for the
selected output connector Output: ready-to-export payload
Connectors:
pohoda  → generate Pohoda XML (RADVYD format for received invoices)
csv  → flat CSV row matching column order in config
json  → clean JSON object
webhook  → POST payload to client’s endpoint URL
Configuration System
Each client has one config row in DB. No code changes needed for new clients.
Fields below confidence_threshold  are flagged for manual review.
Database Schema
{
  "client_id": "uuid",
  "name": "Firma s.r.o.",
  "fields_required": ["vendor_name", "invoice_number", "invoice_date", "total_amo
  "fields_optional": ["po_number", "cost_center"],
  "validation_rules": {
    "vat_format": "SK[0-9]{10}",
    "date_format": "DD.MM.YYYY",
    "allowed_currencies": ["EUR"]
  },
  "output_connector": "pohoda",
  "connector_config": {
    "type": "pohoda",
    "ico": "12345678",
    "export_path": "/exports/pohoda/"
  },
  "language": "sk",
  "confidence_threshold": 0.75
}
-- Clients

--- PAGE 5 ---
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
-- Invoices
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    file_path TEXT NOT NULL,           -- Azure Blob path
    status TEXT DEFAULT 'processing',  -- processing|review|approved|exported|err
    raw_text TEXT,
    extracted JSONB,
    validated JSONB,
    enriched JSONB,
    formatted JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    exported_at TIMESTAMPTZ
);
-- Vendor knowledge base (RAG)
CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID REFERENCES clients(id),
    name TEXT NOT NULL,
    vat_number TEXT,
    iban TEXT,
    category TEXT,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX vendors_embedding_idx ON vendors USING ivfflat (embedding vector_cos
-- Agent execution logs (observability)
CREATE TABLE processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id),
    agent_name TEXT NOT NULL,
    input JSONB,
    output JSONB,
    duration_ms INTEGER,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

--- PAGE 6 ---
FastAPI Endpoints
Frontend Pages (Next.js)
Route
Page
Description
/
Dashboard
Recent invoices, stats, quick upload button
/upload
Upload
Drag & drop PDF, live processing status
/invoices
List
Table view, filter by status/date/vendor
/invoices/[id]
Review
PDF viewer + extracted fields, edit mode, confidence
scores
/config
Config
Field mapping, validation rules, connector setup UI
/vendors
Vendors
Vendor knowledge base management
/stats
Stats
Volume charts, accuracy rates, hours saved
POST   /api/invoices/upload              Upload PDF, trigger pipeline
GET    /api/invoices/                    List invoices (filter by status, date)
GET    /api/invoices/{id}                Get invoice with full extracted data
PUT    /api/invoices/{id}/approve        Approve and trigger export
DELETE /api/invoices/{id}               Soft delete
POST   /api/export/{invoice_id}         Manual export trigger
GET    /api/export/{invoice_id}/preview Preview formatted export payload
GET    /api/config/{client_id}          Get client config
POST   /api/config                      Create/update client config
GET    /api/vendors/                    List vendors in knowledge base
POST   /api/vendors/                    Add vendor
DELETE /api/vendors/{id}               Remove vendor
GET    /api/stats                       Processing stats (volume, accuracy, time 

--- PAGE 7 ---
Development Phases
Phase 1 — Core Pipeline (Week 1–2)
FastAPI project setup + PostgreSQL + Docker Compose
PDF text extraction with PyMuPDF
LangGraph pipeline: Extract + Validate agents only
Basic Next.js: upload page + review page (read-only)
Azure OpenAI connection with Pydantic structured output
Phase 2 — Storage & RAG (Week 2–3)
pgvector setup + vendor embeddings
Enrich agent (vendor matching + deduplication)
Format agent (CSV/JSON first, Pohoda later)
Config system (DB-driven, not hardcoded)
Confidence scores shown in UI with highlight on low-confidence fields
Phase 3 — Connectors & Config UI (Week 3–4)
Pohoda XML export (RADVYD format)
Webhook connector
Config UI in frontend (no-code field mapping)
Vendor management UI
Phase 4 — Polish & Deploy (Week 4)
Docker multi-stage build (frontend + backend)
Azure deployment (VM or Container Apps)
Auth (Clerk or NextAuth)
Processing stats dashboard
Error handling, retry logic, dead-letter queue
README + demo video for portfolio

--- PAGE 8 ---
Environment Variables
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-01
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/invoices_db
# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=
AZURE_STORAGE_CONTAINER=invoice-files
# App
SECRET_KEY=your-secret-key-here
NEXT_PUBLIC_API_URL=http://localhost:8000
# Optional: Azure Document Intelligence (for scanned PDFs)
AZURE_DOC_INTEL_ENDPOINT=
AZURE_DOC_INTEL_KEY=
Key Design Decisions
1. Config-driven, not code-driven Adding a new client = new row in clients table + config
JSON. Zero code changes. Field names, validation rules, output format, connector type
— all in config.
2. pgvector for vendor RAG Instead of re-extracting known vendor data from every
invoice, store vendor embeddings. Enrich agent does similarity search — fast, accurate,
teaches itself over time as you add more vendors.
3. LangGraph for orchestration Easy to add new agents, reorder steps, add conditional
branching (e.g. skip Enrich if vendor not in DB). Full observability via processing_logs
table.
4. Confidence scores on every field Accountants don’t trust black boxes. Showing
confidence score per field + highlighting low-confidence fields builds trust and reduces
errors. Fields below threshold go to manual review.
5. Pohoda-first, then extensible Slovak SMB market first. Pohoda is the dominant

--- PAGE 9 ---
accounting software. Once connector is built as a pluggable class, adding Omega,
Money S3, or Xero is a new class only.
6. PyMuPDF first, Azure Doc Intel as fallback PyMuPDF is free and fast for digital PDFs.
Azure Document Intelligence (paid) is used only for scanned/image PDFs where text
extraction fails.
Monetization Model
Tier
Volume
Price
Starter
Up to 100 invoices/month
€49/month
Pro
Up to 500 invoices/month
€99/month
Business
Unlimited
€199/month
Plus:
One-time setup fee: €300–800 (install, configure, connect to client Pohoda)
Custom connector development: €60/hour
Break-even: 1 paying Pro client covers API costs. Target: 10 Pro clients = ~€990/month
recurring.
Notes for Codex
Use uv  for Python dependency management
Keep LangGraph agents stateless — all state lives in InvoiceState TypedDict
Always use Pydantic models for LLM structured output (never parse raw strings)
Log every agent execution to processing_logs table (input, output, duration)
Never hardcode client-specific logic — always read from config JSON
PDF extraction: try PyMuPDF first ( fitz.open() ), fallback to Azure Doc Intel
All dates stored as ISO 8601 in DB, converted to client locale format on export
Pohoda XML follows RADVYD schema — check Pohoda developer documentation

--- PAGE 10 ---
For local dev: use Docker Compose with postgres + pgvector image
Embeddings: use Azure OpenAI text-embedding-3-small (1536 dimensions)
