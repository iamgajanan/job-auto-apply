-- Webhook event deduplication table.
--
-- Razorpay (and other payment providers) may deliver the same webhook event
-- more than once. This table records every processed event by its provider
-- event ID so the application can detect and skip duplicates safely.
--
-- The unique constraint on (provider, provider_event_id) is the idempotency
-- guarantee: a second delivery of the same event will fail the insert and the
-- caller should treat the conflict as "already processed".

create table public.webhook_events (
  id                  uuid        primary key default gen_random_uuid(),
  provider            text        not null,
  provider_event_id   text        not null,
  event_type          text        not null,
  payment_id          uuid        references public.payments(id) on delete set null,
  raw_payload         jsonb       not null default '{}'::jsonb,
  processed_at        timestamptz not null default timezone('utc', now()),

  constraint webhook_events_provider_event_unique
    unique (provider, provider_event_id)
);

comment on table public.webhook_events is
  'Deduplication log for incoming payment-provider webhooks. '
  'The unique constraint on (provider, provider_event_id) prevents double-processing.';

create index webhook_events_provider_event_idx
  on public.webhook_events(provider, provider_event_id);

create index webhook_events_payment_id_idx
  on public.webhook_events(payment_id);

-- RLS: backend uses service_role connection; no direct client access needed.
alter table public.webhook_events enable row level security;

grant all on public.webhook_events to service_role;
revoke all on public.webhook_events from anon, authenticated;
