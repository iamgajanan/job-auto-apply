begin;

-- Seed authenticated test identities. The auth hardening trigger creates the
-- matching public.profiles rows automatically.
do $$
declare
  u1 uuid := gen_random_uuid();
  u2 uuid := gen_random_uuid();
  s uuid;
begin
  insert into auth.users (id, email, encrypted_password, email_confirmed_at, created_at, updated_at, raw_user_meta_data)
  values
    (u1, 'saved-search-test-1@example.com', 'test', timezone('utc', now()), timezone('utc', now()), timezone('utc', now()), '{"full_name":"Saved Search Test One"}'),
    (u2, 'saved-search-test-2@example.com', 'test', timezone('utc', now()), timezone('utc', now()), timezone('utc', now()), '{"full_name":"Saved Search Test Two"}');

  insert into public.saved_searches (
    user_id, name, platform, job_title, location, experience,
    work_mode, posted_within, easy_apply, alert_enabled, alert_frequency
  ) values (
    u1, 'React Pune', 'naukri', 'React', 'Pune', '5 years',
    'any', 'day', false, true, 'daily'
  ) returning id into s;

  if not exists (
    select 1 from public.saved_searches
    where id = s and user_id = u1 and name = 'React Pune'
  ) then
    raise exception 'saved search insert failed';
  end if;

  update public.saved_searches
  set name = 'React Pune Updated', alert_enabled = false
  where id = s and user_id = u1;

  if not exists (
    select 1 from public.saved_searches
    where id = s and name = 'React Pune Updated' and alert_enabled = false
  ) then
    raise exception 'saved search update failed';
  end if;

  if exists (
    select 1 from public.saved_searches
    where id = s and user_id = u2
  ) then
    raise exception 'saved search ownership isolation failed';
  end if;

  delete from public.saved_searches where id = s and user_id = u1;
  if exists (select 1 from public.saved_searches where id = s) then
    raise exception 'saved search delete failed';
  end if;

  delete from auth.users where id in (u1, u2);
end $$;

rollback;
