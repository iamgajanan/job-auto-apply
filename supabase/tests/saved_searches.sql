begin;

select plan(10);

select has_table('public', 'saved_searches', 'saved_searches table exists');
select has_column('public', 'saved_searches', 'user_id', 'saved_searches.user_id exists');
select has_column('public', 'saved_searches', 'alert_frequency', 'saved_searches.alert_frequency exists');

-- Seed authenticated test identities. The auth hardening trigger creates the
-- matching public.profiles rows automatically.
do $$
declare
  u1 uuid := gen_random_uuid();
  u2 uuid := gen_random_uuid();
begin
  insert into auth.users (id, email, encrypted_password, email_confirmed_at, created_at, updated_at, raw_user_meta_data)
  values
    (u1, 'saved-search-test-1@example.com', 'test', timezone('utc', now()), timezone('utc', now()), timezone('utc', now()), '{"full_name":"Saved Search Test One"}'),
    (u2, 'saved-search-test-2@example.com', 'test', timezone('utc', now()), timezone('utc', now()), timezone('utc', now()), '{"full_name":"Saved Search Test Two"}');

  perform set_config('test.saved_search_user_1', u1::text, true);
  perform set_config('test.saved_search_user_2', u2::text, true);
end $$;

set local role authenticated;
do $$
begin
  perform set_config('request.jwt.claim.sub', current_setting('test.saved_search_user_1'), true);
end $$;

select lives_ok($sql$
  insert into public.saved_searches (
    user_id, name, platform, job_title, location, experience,
    work_mode, posted_within, easy_apply, alert_enabled, alert_frequency
  ) values (
    current_setting('test.saved_search_user_1')::uuid,
    'React Pune', 'naukri', 'React', 'Pune', '5 years',
    'any', 'day', false, true, 'daily'
  )
$sql$, 'user can create a saved search');

select is(
  (select count(*) from public.saved_searches
   where user_id = current_setting('test.saved_search_user_1')::uuid),
  1::bigint,
  'user can read their saved search'
);

select lives_ok($sql$
  update public.saved_searches
  set name = 'React Pune Updated', alert_enabled = false
  where user_id = current_setting('test.saved_search_user_1')::uuid
$sql$, 'user can update their saved search');

select is(
  (select name from public.saved_searches
   where user_id = current_setting('test.saved_search_user_1')::uuid),
  'React Pune Updated',
  'updated saved search is visible to its owner'
);

do $$
begin
  perform set_config('request.jwt.claim.sub', current_setting('test.saved_search_user_2'), true);
end $$;

select is(
  (select count(*) from public.saved_searches),
  0::bigint,
  'user cannot read another user saved search'
);

do $$
begin
  perform set_config('request.jwt.claim.sub', current_setting('test.saved_search_user_1'), true);
end $$;

select lives_ok($sql$
  delete from public.saved_searches
  where user_id = current_setting('test.saved_search_user_1')::uuid
$sql$, 'user can delete their saved search');

select is(
  (select count(*) from public.saved_searches),
  0::bigint,
  'deleted saved search is no longer visible'
);

reset role;

select * from finish();
rollback;
