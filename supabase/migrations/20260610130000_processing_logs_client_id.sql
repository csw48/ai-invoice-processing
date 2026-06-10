-- Scope processing_logs by tenant so /api/stats shows per-client
-- agent timings instead of averages across all tenants.
alter table public.processing_logs
    add column if not exists client_id text;

-- Backfill existing rows via their invoice's client_id.
update public.processing_logs pl
set client_id = i.client_id
from public.invoices i
where i.id = pl.invoice_id
  and pl.client_id is null;

create index if not exists processing_logs_client_id_idx
    on public.processing_logs (client_id);
