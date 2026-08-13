CREATE OR REPLACE FUNCTION public.consume_search_quota(
  p_user_id uuid,
  p_platform text,
  p_job_title text,
  p_location text,
  p_units integer DEFAULT 1,
  p_request_id uuid DEFAULT gen_random_uuid(),
  p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS TABLE(
  quota_allocation_id uuid,
  granted_searches integer,
  used_searches integer,
  remaining_searches integer
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
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

  update public.quota_allocations AS qa
  set used_searches = qa.used_searches + p_units,
      updated_at = timezone('utc', now())
  where qa.id = v_allocation.id
  returning qa.* into v_allocation;

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
$function$;
