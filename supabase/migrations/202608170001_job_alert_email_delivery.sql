alter table public.saved_search_alert_runs
  add column if not exists email_status text not null default 'not_sent'
    check (email_status in ('not_sent', 'queued', 'sent', 'failed')),
  add column if not exists email_error text;

create table if not exists public.saved_search_alert_email_deliveries (
  id uuid primary key default gen_random_uuid(),
  alert_run_id uuid not null unique references public.saved_search_alert_runs(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  status text not null default 'queued'
    check (status in ('queued', 'sending', 'sent', 'failed')),
  attempts integer not null default 0,
  provider_message_id text,
  error_message text,
  created_at timestamptz not null default timezone('utc', now()),
  started_at timestamptz,
  completed_at timestamptz,
  sent_at timestamptz
);

create index if not exists saved_search_alert_email_deliveries_queue_idx
  on public.saved_search_alert_email_deliveries(status, created_at);

alter table public.saved_search_alert_email_deliveries enable row level security;

create policy "Users can read their own alert email deliveries"
on public.saved_search_alert_email_deliveries
for select
to authenticated
using ((select auth.uid()) = user_id);

grant select on public.saved_search_alert_email_deliveries to authenticated;
grant all on public.saved_search_alert_email_deliveries to service_role;
