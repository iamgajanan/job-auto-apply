-- Job Auto Apply - initial application schema.
--
-- Supabase Auth owns auth.users. Application-specific user data lives in
-- public.profiles and references auth.users(id).
--
-- All prices are stored in INR paise so payment amounts are integer-safe.

create extension if not exists pgcrypto;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table public.plans (
  code text primary key,
  name text not null,
  price_inr_paise bigint not null default 0 check (price_inr_paise >= 0),
  search_limit integer not null check (search_limit > 0),
  billing_interval text null check (
    billing_interval in ('monthly', 'yearly')
    or billing_interval is null
  ),
  is_active boolean not null default true,
  sort_order integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

comment on table public.plans is
  'Product plans and their search quotas. Billing interval is intentionally nullable until the payment model is finalized.';

insert into public.plans (
  code,
  name,
  price_inr_paise,
  search_limit,
  billing_interval,
  sort_order
)
values
  ('free', 'Free', 0, 50, null, 0),
  ('starter', 'Starter', 29900, 100, null, 1),
  ('growth', 'Growth', 59900, 500, null, 2),
  ('pro', 'Pro', 99900, 1000, null, 3),
  ('business', 'Business', 149900, 2000, null, 4)
on conflict (code) do update
set
  name = excluded.name,
  price_inr_paise = excluded.price_inr_paise,
  search_limit = excluded.search_limit,
  sort_order = excluded.sort_order,
  updated_at = timezone('utc', now());

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text,
  role text not null default 'user' check (role in ('user', 'super_admin')),
  status text not null default 'active' check (status in ('active', 'suspended', 'deleted')),
  plan_code text not null default 'free' references public.plans(code),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

comment on table public.profiles is
  'Application profile linked one-to-one to a Supabase Auth user. Passwords and authentication secrets are never stored here.';

create table public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_code text not null references public.plans(code),
  status text not null default 'pending' check (
    status in ('pending', 'active', 'cancelled', 'expired', 'past_due')
  ),
  provider text,
  provider_customer_id text,
  provider_subscription_id text,
  started_at timestamptz,
  ends_at timestamptz,
  cancelled_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint subscriptions_provider_subscription_unique
    unique (provider, provider_subscription_id)
);

create index subscriptions_user_id_idx
  on public.subscriptions(user_id);

create index subscriptions_status_idx
  on public.subscriptions(status);

create table public.quota_allocations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_code text not null references public.plans(code),
  granted_searches integer not null check (granted_searches > 0),
  used_searches integer not null default 0 check (
    used_searches >= 0 and used_searches <= granted_searches
  ),
  source text not null check (
    source in ('signup', 'payment', 'admin', 'migration')
  ),
  starts_at timestamptz not null default timezone('utc', now()),
  ends_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index quota_allocations_user_id_idx
  on public.quota_allocations(user_id);

create index quota_allocations_active_idx
  on public.quota_allocations(user_id, starts_at, ends_at);

create table public.search_usage (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  quota_allocation_id uuid references public.quota_allocations(id) on delete set null,
  platform text not null check (platform in ('linkedin', 'naukri')),
  job_title text not null,
  location text not null,
  units integer not null default 1 check (units > 0),
  request_id uuid not null default gen_random_uuid(),
  requested_at timestamptz not null default timezone('utc', now()),
  metadata jsonb not null default '{}'::jsonb,
  constraint search_usage_request_id_unique unique (request_id)
);

create index search_usage_user_requested_at_idx
  on public.search_usage(user_id, requested_at desc);

create table public.payments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_code text not null references public.plans(code),
  provider text not null default 'razorpay',
  provider_order_id text,
  provider_payment_id text,
  provider_signature text,
  amount_inr_paise bigint not null check (amount_inr_paise > 0),
  currency text not null default 'INR',
  status text not null check (
    status in ('created', 'authorized', 'captured', 'failed', 'refunded', 'partially_refunded')
  ),
  paid_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint payments_provider_order_unique
    unique (provider, provider_order_id),
  constraint payments_provider_payment_unique
    unique (provider, provider_payment_id)
);

create index payments_user_id_idx
  on public.payments(user_id);

create index payments_status_idx
  on public.payments(status);

create trigger plans_set_updated_at
before update on public.plans
for each row execute function public.set_updated_at();

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create trigger subscriptions_set_updated_at
before update on public.subscriptions
for each row execute function public.set_updated_at();

create trigger quota_allocations_set_updated_at
before update on public.quota_allocations
for each row execute function public.set_updated_at();

create trigger payments_set_updated_at
before update on public.payments
for each row execute function public.set_updated_at();

-- RLS is enabled now even though the backend will use a trusted database
-- connection. This protects the same tables if the Supabase Data API is used
-- later by the frontend.
alter table public.plans enable row level security;
alter table public.profiles enable row level security;
alter table public.subscriptions enable row level security;
alter table public.quota_allocations enable row level security;
alter table public.search_usage enable row level security;
alter table public.payments enable row level security;

create policy "Active plans are publicly readable"
on public.plans
for select
to anon, authenticated
using (is_active = true);

create policy "Users can read their own profile"
on public.profiles
for select
to authenticated
using ((select auth.uid()) = id);

create policy "Users can read their own subscriptions"
on public.subscriptions
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can read their own quota allocations"
on public.quota_allocations
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can read their own search usage"
on public.search_usage
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can read their own payments"
on public.payments
for select
to authenticated
using ((select auth.uid()) = user_id);

-- Explicitly grant only the read operations needed by the public Data API.
grant select on public.plans to anon, authenticated;
grant select on public.profiles to authenticated;
grant select on public.subscriptions to authenticated;
grant select on public.quota_allocations to authenticated;
grant select on public.search_usage to authenticated;
grant select on public.payments to authenticated;

grant all on public.plans to service_role;
grant all on public.profiles to service_role;
grant all on public.subscriptions to service_role;
grant all on public.quota_allocations to service_role;
grant all on public.search_usage to service_role;
grant all on public.payments to service_role;
