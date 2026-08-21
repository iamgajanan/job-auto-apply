# Job Auto Apply Backend — Phase 1 Complete

> Canonical backend status/reference for the current `just-scrapping` branch.

## Status

**Phase 1: COMPLETE**

The backend currently provides the production foundation used by the JobFinder frontend: authentication, user profiles, plans and quotas, LinkedIn/Naukri search, saved searches, scheduled alerts, new-job detection, Resend email delivery, viewed-job tracking, Razorpay payments, database migrations, CI/CD and Raspberry Pi deployment.

## Architecture

```text
Next.js frontend
      |
      v
Same-origin/proxy layer
      |
      v
FastAPI backend :8004
      |
      +--> Supabase Auth
      +--> Supabase PostgreSQL
      +--> Redis
      +--> Razorpay
      +--> Resend
      +--> LinkedIn Playwright provider
      +--> Naukri Playwright provider
```

Runtime:

- Raspberry Pi 5 ARM64
- FastAPI/Uvicorn managed by `job-auto-apply.service`
- Working backend branch: `just-scrapping`
- Application directory: `/home/iamgajanan/Projects/job-auto-apply`
- Backend virtual environment: `backend/.venv`
- Backend port on the Pi: `8004`
- Public backend is exposed through the existing Cloudflare setup.

## Authentication

Supabase Auth owns credentials and sessions. FastAPI owns application authorization and profile/plan/quota state.

Implemented:

- signup
- login
- token refresh
- logout
- current-user lookup
- password reset
- password update
- active/inactive account enforcement
- super-admin allowlist
- admin-only operations

The active authentication adapter uses a reusable Supabase Auth HTTP client. Authentication/profile lookups are short-lived cached and bounded. Missing application profiles can be provisioned from a valid authenticated identity.

## Database

Supabase PostgreSQL is the production system of record.

Core data areas:

```text
profiles
plans
subscriptions
quota_allocations
search_usage
payments
payment_refunds
webhook_events
admin_allowlist
saved_searches
alert runs / seen jobs
viewed_jobs
```

Database changes are versioned in `supabase/migrations/` and applied by deployment CI. RLS/user isolation is part of the design.

Important distinction:

- `auth.users` = Supabase identity/credentials.
- `public.profiles` and application tables = application data.
- Deleting an application profile does not necessarily delete the Supabase Auth identity.
- No migration is required merely because application data/users were deleted; migrations are for schema changes.

## Plans and quota

| Plan | Price | Search allocation |
|---|---:|---:|
| Free | ₹0 | 50 |
| Starter | ₹299 | 100 |
| Growth | ₹599 | 500 |
| Pro | ₹999 | 1,000 |
| Business | ₹1,499 | 2,000 |

Rules:

- Quota is checked/consumed before expensive interactive scraping.
- Super admins are not limited by normal user quota.
- A successful paid upgrade replaces the active quota allocation instead of adding the old allocation to the new one.
- Free 50 → 100 becomes 100, not 150.
- 100 → 2,000 becomes 2,000, not 2,150.
- Monthly paid-plan upgrades are prorated for the current month. Example: ₹299 → ₹599 charges ₹300 now; ₹599 is the resulting plan for the next billing cycle.
- Payment success invalidates the profile cache so the new plan/quota is immediately visible.

## Job search

Supported providers:

- LinkedIn Playwright provider
- Naukri Playwright provider

Filters include platform, title, location, experience, work mode, freshness and Easy Apply where supported.

Interactive search consumes quota. Alert searches do not consume the interactive quota.

Search performance improvements completed:

- exact-search result caching
- reduced unnecessary provider page/scroll work
- concurrent provider execution for multi-provider searches
- reusable database/auth connections
- controlled upstream error handling

External provider scraping can still take longer than ordinary database APIs because it depends on browser automation and provider response time.

## Saved searches

Users can create, edit, delete and reuse saved searches.

Each saved search can store:

- name
- platform
- job title
- location
- experience
- work mode
- posting freshness
- Easy Apply preference
- alert enabled/disabled state
- Daily/Weekly frequency

Ownership is enforced. Criteria changes reset alert-seen history so previous jobs do not incorrectly suppress future matches.

## Job alerts

### Scheduling

- Daily: 09:00 IST.
- Weekly: Monday 09:00 IST.
- Scheduler runs from the FastAPI application lifecycle.
- Queue dispatch uses atomic locking to avoid duplicate runs.

### Execution

```text
scheduled run
   ↓
queued alert
   ↓
execute saved-search provider search
   ↓
fingerprint jobs
   ↓
compare against saved-search seen history
   ↓
calculate new-job count
   ↓
persist run result
   ↓
email when new jobs exist
```

### Email

Resend is server-side only.

Required runtime configuration:

```text
RESEND_API_KEY
RESEND_FROM_EMAIL
```

The email includes job title, company, location and apply link. Delivery state is persisted and failed delivery is retried up to three times.

### Manual Test Alert

The manual test alert uses the same alert pipeline but completes synchronously from the frontend's perspective. The frontend no longer polls status/jobs repeatedly while waiting for the mail.

After the test completes, the UI refreshes the alert result once.

## Viewed jobs

The application tracks only **Viewed**.

Implemented:

- mark a job viewed
- update viewed timestamp when reopened
- user-scoped viewed history
- frontend card badge/count
- dedicated viewed-jobs screen
- no repeated job-search request when a job becomes viewed

The system intentionally does **not** infer:

- Applied
- Application submitted
- Interview
- Rejected
- Offer

## Payments

Razorpay Test Mode is used during development.

Server-side responsibilities:

1. create payment order
2. store payment state
3. validate Razorpay signature
4. fulfil captured payment
5. activate plan/quota
6. update subscription state
7. invalidate cached profile/plan data
8. handle failed payments
9. handle refunds
10. deduplicate repeated webhook events

Secrets remain server-side:

```text
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
```

## CI/CD and deployment

```text
Git push
   ↓
just-scrapping
   ↓
GitHub Actions
   ↓
Raspberry Pi self-hosted ARM64 runner
   ↓
Supabase migration validation/application
   ↓
backend checks
   ↓
FastAPI service restart
   ↓
health/smoke validation
```

Runtime `.env`, browser session data, Redis data and Cloudflare configuration are not committed to Git.

## Performance hardening completed

Recent work addressed the latency/duplicate-request problems observed in browser DevTools:

- Supabase Auth connection reuse/warm-up.
- PostgreSQL pool reuse/warm-up.
- 60-second auth verification cache.
- 30-second profile cache.
- payment-triggered profile-cache invalidation.
- saved-search backend/frontend request deduplication.
- viewed-job request deduplication.
- combined alert overview reads.
- synchronous manual test alerts.
- exact-search caching.
- reduced scraper depth/scrolling.
- concurrent multi-provider search execution.

The target is low latency for authenticated/database APIs. Scraping endpoints remain dependent on external provider/browser timing.

## Testing policy

Use focused tests relevant to the change. The project does not require unrelated suites for every modification.

Coverage completed across the phases includes authentication, database isolation, quota ordering, payments, webhook idempotency, saved-search CRUD, alert scheduling, new-job fingerprinting, email rendering, viewed-job behavior and performance-sensitive authenticated paths.

## Branch policy

- Backend working/integration branch: `just-scrapping`.
- Frontend working/integration branch: `main`.
- Do not move backend work to `main` unless the branch strategy is intentionally changed.

## Phase 1 completion note

**Backend Phase 1 is complete.** This document records the state reached after the authentication, database, billing, search, saved-search, alert, email, viewed-job and performance work completed so far.
