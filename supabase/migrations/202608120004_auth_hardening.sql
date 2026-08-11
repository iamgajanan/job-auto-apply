-- Auth hardening and recovery for users created before/around the auth trigger rollout.
-- Credentials remain owned by Supabase Auth; application data remains in public.profiles.

-- These functions are trusted backend/database functions and must not be callable
-- through the public Supabase Data API.
revoke execute on function public.handle_new_auth_user() from public, anon, authenticated;
revoke execute on function public.consume_search_quota(uuid, text, text, text, integer, uuid, jsonb) from public, anon, authenticated;
grant execute on function public.consume_search_quota(uuid, text, text, text, integer, uuid, jsonb) to service_role;

-- Keep the generic timestamp trigger deterministic when objects are referenced
-- by an unqualified name inside the function body.
alter function public.set_updated_at() set search_path = '';

-- Recover application profiles for any Auth users that existed before the
-- profile trigger/migration was applied. This is idempotent.
insert into public.profiles (id, email, full_name, role, status, plan_code)
select
  u.id,
  lower(u.email),
  nullif(u.raw_user_meta_data ->> 'full_name', ''),
  case
    when exists (
      select 1
      from public.admin_allowlist a
      where lower(a.email) = lower(u.email)
        and a.is_active = true
    ) then 'super_admin'
    else 'user'
  end,
  'active',
  'free'
from auth.users u
on conflict (id) do update
set email = excluded.email,
    full_name = coalesce(excluded.full_name, public.profiles.full_name),
    role = case
      when exists (
        select 1
        from public.admin_allowlist a
        where lower(a.email) = lower(excluded.email)
          and a.is_active = true
      ) then 'super_admin'
      else public.profiles.role
    end,
    updated_at = timezone('utc', now());

-- Every existing user must have one initial free allocation if they do not
-- already have quota. This is also idempotent.
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
    select 1
    from public.quota_allocations qa
    where qa.user_id = p.id
  );
