-- Step 1 (classification) output: document type + sender/recipient.
-- Documents classified as "other"/"junk" short-circuit the pipeline and carry
-- the new statuses 'redirect'/'discarded'.
alter table public.invoices
    add column if not exists classification jsonb;
