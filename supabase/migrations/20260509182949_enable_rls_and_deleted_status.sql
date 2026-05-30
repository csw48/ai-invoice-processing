alter table public.clients enable row level security;
alter table public.invoices enable row level security;
alter table public.vendors enable row level security;
alter table public.processing_logs enable row level security;

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
                'deleted'::text
            ]
        )
    );
