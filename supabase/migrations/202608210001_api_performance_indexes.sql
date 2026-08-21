-- Hot authenticated API paths. These indexes avoid sequential scans as the
-- user, payment, alert and viewed-job tables grow.
create index if not exists profiles_email_lower_idx
  on public.profiles (lower(email));

create index if not exists quota_allocations_active_user_idx
  on public.quota_allocations (user_id, starts_at desc, ends_at);

create index if not exists payments_user_created_idx
  on public.payments (user_id, created_at desc);

create index if not exists payments_order_user_idx
  on public.payments (provider, provider_order_id, user_id);

create index if not exists saved_search_alert_runs_user_created_idx
  on public.saved_search_alert_runs (user_id, created_at desc);

create index if not exists saved_search_alert_runs_search_created_idx
  on public.saved_search_alert_runs (saved_search_id, created_at desc);

create index if not exists saved_search_alert_jobs_search_seen_idx
  on public.saved_search_alert_jobs (saved_search_id, first_seen_at desc);

create index if not exists saved_search_alert_email_queued_idx
  on public.saved_search_alert_email_deliveries (status, created_at);

create index if not exists viewed_jobs_user_platform_job_idx
  on public.viewed_jobs (user_id, platform, job_id);
