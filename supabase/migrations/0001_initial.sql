create extension if not exists "pgcrypto";
create extension if not exists vector;

create table if not exists clients (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    config jsonb not null,
    created_at timestamptz default now()
);

create table if not exists invoices (
    id uuid primary key default gen_random_uuid(),
    client_id uuid references clients(id),
    file_path text not null,
    status text default 'processing' check (status in ('processing','review','approved','exported','error')),
    raw_text text,
    extracted jsonb,
    validated jsonb,
    enriched jsonb,
    formatted jsonb,
    created_at timestamptz default now(),
    exported_at timestamptz
);

create table if not exists vendors (
    id uuid primary key default gen_random_uuid(),
    client_id uuid references clients(id),
    name text not null,
    vat_number text,
    iban text,
    category text,
    embedding vector(1536),
    metadata jsonb,
    created_at timestamptz default now()
);

create index if not exists vendors_embedding_idx on vendors using ivfflat (embedding vector_cosine_ops);
create index if not exists vendors_client_vat_idx on vendors (client_id, vat_number);

create table if not exists processing_logs (
    id uuid primary key default gen_random_uuid(),
    invoice_id uuid references invoices(id),
    agent_name text not null,
    input jsonb,
    output jsonb,
    duration_ms integer,
    error text,
    created_at timestamptz default now()
);
