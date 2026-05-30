-- Per-tenant data isolation: scope invoices and vendors by client_id.
--
-- The tenant key is the verified Clerk claim (org_id/sub) or "default", the same
-- TEXT key used by client_configs.id. The original columns were uuid REFERENCES
-- clients(id); switch them to TEXT and make them required so every row is owned
-- by exactly one tenant. Existing rows are backfilled to "default".

-- Invoices ---------------------------------------------------------------------
alter table if exists public.invoices
    drop constraint if exists invoices_client_id_fkey;

alter table if exists public.invoices
    alter column client_id type text using client_id::text;

update public.invoices set client_id = 'default' where client_id is null;

alter table if exists public.invoices
    alter column client_id set default 'default',
    alter column client_id set not null;

create index if not exists invoices_client_id_idx on public.invoices (client_id);

-- Vendors ----------------------------------------------------------------------
alter table if exists public.vendors
    drop constraint if exists vendors_client_id_fkey;

alter table if exists public.vendors
    alter column client_id type text using client_id::text;

update public.vendors set client_id = 'default' where client_id is null;

alter table if exists public.vendors
    alter column client_id set default 'default',
    alter column client_id set not null;

-- vendors_client_vat_idx (client_id, vat_number) already exists from 0001.
