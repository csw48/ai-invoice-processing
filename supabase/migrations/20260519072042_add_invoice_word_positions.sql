alter table public.invoices
    add column if not exists word_positions jsonb;
