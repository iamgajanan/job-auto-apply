begin;

select plan(18);

select has_table('public', 'plans', 'plans table exists');
select has_table('public', 'profiles', 'profiles table exists');
select has_table('public', 'subscriptions', 'subscriptions table exists');
select has_table('public', 'quota_allocations', 'quota_allocations table exists');
select has_table('public', 'search_usage', 'search_usage table exists');
select has_table('public', 'payments', 'payments table exists');

select has_column('public', 'profiles', 'id', 'profiles.id exists');
select has_column('public', 'profiles', 'role', 'profiles.role exists');
select has_column('public', 'profiles', 'plan_code', 'profiles.plan_code exists');
select has_column('public', 'quota_allocations', 'granted_searches', 'quota grant exists');
select has_column('public', 'quota_allocations', 'used_searches', 'quota usage exists');
select has_column('public', 'search_usage', 'request_id', 'search request id exists');
select has_column('public', 'payments', 'provider_order_id', 'payment order id exists');
select has_column('public', 'payments', 'provider_payment_id', 'payment id exists');

select is((select count(*) from public.plans), 5::bigint, 'five plans are seeded');
select is((select search_limit from public.plans where code = 'free'), 50, 'free plan has 50 searches');
select is((select price_inr_paise from public.plans where code = 'starter'), 29900::bigint, 'starter plan is INR 299');
select is((select search_limit from public.plans where code = 'business'), 2000, 'business plan has 2000 searches');

select * from finish();
rollback;
