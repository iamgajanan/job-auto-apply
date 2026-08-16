alter table public.saved_searches
  add column if not exists alert_next_run_at timestamptz,
  add column if not exists alert_last_run_at timestamptz;

create index if not exists saved_searches_alert_due_idx
  on public.saved_searches(alert_enabled, alert_next_run_at)
  where alert_enabled = true;

create table if not exists public.saved_search_alert_runs (
  id uuid primary key default gen_random_uuid(),
  saved_search_id uuid not null references public.saved_searches(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  scheduled_for timestamptz not null,
  status text not null default 'queued' check (status in ('queued', 'running', 'completed', 'failed', 'skipped')),
  created_at timestamptz not null default timezone('utc', now()),
  started_at timestamptz,
  completed_at timestamptz,
  error_message text
);

create index if not exists saved_search_alert_runs_search_created_idx
  on public.saved_search_alert_runs(saved_search_id, created_at desc);

create index if not exists saved_search_alert_runs_user_created_idx
  on public.saved_search_alert_runs(user_id, created_at desc);

alter table public.saved_search_alert_runs enable row level security;

create policy "Users can read their own saved search alert runs"
on public.saved_search_alert_runs
for select
to authenticated
using ((select auth.uid()) = user_id);

grant select on public.saved_search_alert_runs to authenticated;
grant all on public.saved_search_alert_runs to service_role;
