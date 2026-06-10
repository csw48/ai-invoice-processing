-- The classification feature (20260530120000) introduced the 'redirect'
-- (document_type "other") and 'discarded' (document_type "junk") statuses but
-- never widened invoices_status_check, so saving any non-invoice document
-- violated the constraint. Recreate the check with the full status set.
alter table public.invoices drop constraint if exists invoices_status_check;
alter table public.invoices add constraint invoices_status_check
    check (
        status = any (
            array[
                'processing'::text,
                'review'::text,
                'approved'::text,
                'exported'::text,
                'error'::text,
                'deleted'::text,
                'redirect'::text,
                'discarded'::text
            ]
        )
    );
