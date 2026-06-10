-- Track which extracted fields a reviewer manually corrected.
-- Feeds per-field extraction-accuracy stats on /api/stats.
alter table invoices
  add column if not exists edited_fields jsonb not null default '[]'::jsonb;
