-- Payment history and refund ledger.
-- Refund rows are kept separately so partial refunds can be calculated safely
-- instead of relying only on the current payment status.

create table public.payment_refunds (
  id uuid primary key default gen_random_uuid(),
  payment_id uuid not null references public.payments(id) on delete cascade,
  provider text not null default 'razorpay',
  provider_refund_id text not null,
  amount_inr_paise bigint not null check (amount_inr_paise > 0),
  currency text not null default 'INR',
  status text not null check (status in ('created', 'processed', 'failed')),
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  constraint payment_refunds_provider_refund_unique
    unique (provider, provider_refund_id)
);

create index payment_refunds_payment_id_idx
  on public.payment_refunds(payment_id);

create index payment_refunds_status_idx
  on public.payment_refunds(status);

create trigger payment_refunds_set_updated_at
before update on public.payment_refunds
for each row execute function public.set_updated_at();

alter table public.payment_refunds enable row level security;

grant all on public.payment_refunds to service_role;
revoke all on public.payment_refunds from anon, authenticated;

-- Backend-only payment history queries.
grant select on public.payment_refunds to service_role;
