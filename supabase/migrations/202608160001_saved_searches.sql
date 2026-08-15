create table if not exists public.saved_searches (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null check (char_length(name) between 1 and 100),
  platform text not null check (platform in ('linkedin', 'naukri')),
  job_title text not null check (char_length(job_title) between 1 and 200),
  location text not null check (char_length(location) between 1 and 200),
  experience text,
  work_mode text check (work_mode in ('remote', 'onsite', 'hybrid', 'any') or work_mode is null),
  posted_within text,
  easy_apply boolean not null default false,
  alert_enabled boolean not null default false,
  alert_frequency text check (alert_frequency in ('daily', 'weekly') or alert_frequency is null),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index if not exists saved_searches_user_id_updated_at_idx
  on public.saved_searches(user_id, updated_at desc);

create trigger saved_searches_set_updated_at
before update on public.saved_searches
for each row execute function public.set_updated_at();

alter table public.saved_searches enable row level security;

create policy "Users can read their own saved searches"
on public.saved_searches
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can insert their own saved searches"
on public.saved_searches
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy "Users can update their own saved searches"
on public.saved_searches
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "Users can delete their own saved searches"
on public.saved_searches
for delete
to authenticated
using ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.saved_searches to authenticated;
grant all on public.saved_searches to service_role;
