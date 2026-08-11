-- Authentication/profile bootstrap, admin allowlist, and atomic search-quota consumption.
-- Supabase Auth remains the source of truth for credentials and sessions.

create table public.admin_allowlist (
  email text primary key,
  is_active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now())
);

comment on table public.admin_allowlist is
  'Email addresses allowed to receive the super_admin application role. Credentials are still managed by Supabase Auth.';

alter table public.admin_allowlist enable row level security;

grant select on public.admin_allowlist to service_role;

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, email, full_name, role, status, plan_code)
  values (
    new.id,
    lower(new.email),
    nullif(new.raw_user_meta_data ->> 'full_name', ''),
    'user',
    'active',
    'free'
  )
  on conflict (id) do update
    set email = excluded.email,
        full_name = coalesce(excluded.full_name, public.profiles.full_name),
        updated_at = timezone('utc', now());

  insert into public.quota_allocations (
    user_id,
    plan_code,
    granted_searches,
    source,
    starts_at
  )
  select
    new.id,
    p.code,
    p.search_limit,
    'signup',
    timezone('utc', now())
  from public.plans p
  where p.code = 'free'
    and not exists (
      select 1
      from public.quota_allocations qa
      where qa.user_id = new.id
    );

  return new;
end;
$$;

revoke all on function public.handle_new_auth_user() from public;

 drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_auth_user();

-- Backfill users that existed before the auth trigger was installed.
insert into public.profiles (id, email, full_name, role, status, plan_code)
select
  u.id,
  lower(u.email),
  nullif(u.raw_user_meta_data ->> 'full_name', ''),
  'user',
  'active',
  'free'
from auth.users u
on conflict (id) do update
set email = excluded.email,
    full_name = coalesce(excluded.full_name, public.profiles.full_name),
    updated_at = timezone('utc', now());

insert into public.quota_allocations (
  user_id,
  plan_code,
  granted_searches,
  source,
  starts_at
)
select
  p.id,
  'free',
  free_plan.search_limit,
  'migration',
  timezone('utc', now())
from public.profiles p
cross join public.plans free_plan
where free_plan.code = 'free'
  and not exists (
    select 1 from public.quota_allocations qa where qa.user_id = p.id
  );

create or replace function public.consume_search_quota(
  p_user_id uuid,
  p_platform text,
  p_job_title text,
  p_location text,
  p_units integer default 1,
  p_request_id uuid default gen_random_uuid(),
  p_metadata jsonb default '{}'::jsonb
)
returns table (
  quota_allocation_id uuid,
  granted_searches integer,
  used_searches integer,
  remaining_searches integer
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_allocation public.quota_allocations%rowtype;
begin
  if p_user_id is null then
    raise exception 'user id is required';
  end if;

  if p_units <= 0 then
    raise exception 'units must be greater than zero';
  end if;

  if p_platform not in ('linkedin', 'naukri') then
    raise exception 'unsupported platform';
  end if;

  select qa.*
  into v_allocation
  from public.quota_allocations qa
  where qa.user_id = p_user_id
    and qa.starts_at <= timezone('utc', now())
    and (qa.ends_at is null or qa.ends_at > timezone('utc', now()))
    and qa.used_searches + p_units <= qa.granted_searches
  order by qa.starts_at asc, qa.created_at asc
  for update
  limit 1;

  if not found then
    raise exception 'search quota exceeded';
  end if;

  update public.quota_allocations
  set used_searches = used_searches + p_units,
      updated_at = timezone('utc', now())
  where id = v_allocation.id
  returning * into v_allocation;

  insert into public.search_usage (
    user_id,
    quota_allocation_id,
    platform,
    job_title,
    location,
    units,
    request_id,
    metadata
  ) values (
    p_user_id,
    v_allocation.id,
    p_platform,
    p_job_title,
    p_location,
    p_units,
    p_request_id,
    coalesce(p_metadata, '{}'::jsonb)
  );

  return query
  select
    v_allocation.id,
    v_allocation.granted_searches,
    v_allocation.used_searches,
    v_allocation.granted_searches - v_allocation.used_searches;
end;
$$;

revoke all on function public.consume_search_quota(uuid, text, text, text, integer, uuid, jsonb) from public;
grant execute on function public.consume_search_quota(uuid, text, text, text, integer, uuid, jsonb) to service_role;

-- Keep direct client writes disabled; application mutations happen through the trusted backend.
revoke insert, update, delete on public.admin_allowlist from anon, authenticated;
revoke insert, update, delete on public.profiles from anon, authenticated;
revoke insert, update, delete on public.subscriptions from anon, authenticated;
revoke insert, update, delete on public.quota_allocations from anon, authenticated;
revoke insert, update, delete on public.search_usage from anon, authenticated;
revoke insert, update, delete on public.payments from anon, authenticated;
