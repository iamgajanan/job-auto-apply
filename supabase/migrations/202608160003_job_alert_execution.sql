alter table public.saved_search_alert_runs
  add column if not exists new_jobs_count integer not null default 0,
  add column if not exists result_summary jsonb;

create table if not exists public.saved_search_alert_jobs (
  id uuid primary key default gen_random_uuid(),
  saved_search_id uuid not null references public.saved_searches(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  fingerprint text not null,
  job_data jsonb not null,
  first_seen_at timestamptz not null default timezone('utc', now()),
  last_seen_at timestamptz not null default timezone('utc', now()),
  unique(saved_search_id, fingerprint)
);

create index if not exists saved_search_alert_jobs_search_seen_idx
  on public.saved_search_alert_jobs(saved_search_id, first_seen_at desc);

create index if not exists saved_search_alert_jobs_user_seen_idx
  on public.saved_search_alert_jobs(user_id, first_seen_at desc);

alter table public.saved_search_alert_jobs enable row level security;

create policy "Users can read their own saved search alert jobs"
on public.saved_search_alert_jobs
for select
to authenticated
using ((select auth.uid()) = user_id);

grant select on public.saved_search_alert_jobs to authenticated;
grant all on public.saved_search_alert_jobs to service_role;
