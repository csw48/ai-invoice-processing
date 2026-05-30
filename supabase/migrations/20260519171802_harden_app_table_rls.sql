-- The app's invoice data is server-owned. The browser talks to FastAPI, and
-- FastAPI uses the Supabase service role key server-side. Do not expose these
-- tables through anon/authenticated Data API access.

alter table if exists public.clients enable row level security;
alter table if exists public.invoices enable row level security;
alter table if exists public.vendors enable row level security;
alter table if exists public.processing_logs enable row level security;
alter table if exists public.client_configs enable row level security;

revoke all on table public.clients from anon, authenticated, public;
revoke all on table public.invoices from anon, authenticated, public;
revoke all on table public.vendors from anon, authenticated, public;
revoke all on table public.processing_logs from anon, authenticated, public;
revoke all on table public.client_configs from anon, authenticated, public;

grant all on table public.clients to service_role;
grant all on table public.invoices to service_role;
grant all on table public.vendors to service_role;
grant all on table public.processing_logs to service_role;
grant all on table public.client_configs to service_role;

update storage.buckets
set public = false
where id = 'invoice-files';
