create table if not exists public.viewed_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  platform text not null check (platform in ('linkedin', 'naukri')),
  job_id text not null,
  job_data jsonb not null default '{}'::jsonb,
  viewed_at timestamptz not null default timezone('utc', now()),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  unique (user_id, platform, job_id)
);

create index if not exists viewed_jobs_user_viewed_idx on public.viewed_jobs(user_id, viewed_at desc);
create index if not exists viewed_jobs_user_platform_job_idx on public.viewed_jobs(user_id, platform, job_id);

alter table public.viewed_jobs enable row level security;

create policy "Users can read their own viewed jobs"
on public.viewed_jobs for select to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can insert their own viewed jobs"
on public.viewed_jobs for insert to authenticated
with check ((select auth.uid()) = user_id);

grant select, insert on public.viewed_jobs to authenticated;
grant all on public.viewed_jobs to service_role;
