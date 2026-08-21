# JobFinder — Complete Project Reference

> **Project Phase 1: COMPLETE**  
> Backend integration branch: `just-scrapping`  
> Frontend integration branch: `main`

This document is the single cross-repository reference for the JobFinder project. It combines the current backend, frontend, database, authentication, job search, saved-search, alert, email, viewed-job, payment, deployment and performance architecture.

---

## 1. Product purpose

JobFinder is a job-search SaaS application that lets a user:

1. create an account and sign in;
2. search supported job platforms using filters;
3. see plan/quota usage;
4. purchase or upgrade a search plan;
5. save reusable searches;
6. schedule Daily/Weekly alerts for saved searches;
7. manually test an alert without waiting for the scheduled time;
8. receive email notifications when new jobs are detected;
9. review alert history and newly detected jobs;
10. mark jobs as Viewed and review viewed jobs.

The product intentionally does **not** claim that opening an external job link means the user applied. Application submission, interview, rejection and offer status are therefore not tracked as factual states.

---

## 2. Repositories and branches

| Area | Repository | Working branch |
|---|---|---|
| Backend | `iamgajanan/job-auto-apply` | `just-scrapping` |
| Frontend | `iamgajanan/jobfinder` | `main` |

The backend branch is the integration/deployment branch for backend work. The frontend branch is the integration branch for frontend work.

---

## 3. High-level architecture

```text
                    USER BROWSER
                         |
                         v
                  Next.js / React UI
                         |
                         | same-origin application proxy
                         v
                    FastAPI backend
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
 Supabase Auth    Supabase PostgreSQL    Redis
        |                |                |
        +----------------+----------------+
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
      Razorpay         Resend       Job Providers
                                     /         \
                                LinkedIn      Naukri
                                Playwright    Playwright
```

Production backend runtime currently runs on a Raspberry Pi 5 ARM64 and is managed by `job-auto-apply.service`. Cloudflare provides the existing public exposure path.

---

## 4. Backend architecture

### Main responsibilities

The backend is authoritative for:

- authentication verification
- application roles/status
- profiles
- plans and quotas
- search-quota consumption
- job provider orchestration
- saved-search persistence
- alert scheduling/execution
- new-job fingerprinting
- email delivery state
- payment verification/fulfilment
- webhook idempotency
- viewed-job persistence
- user isolation and authorization

### Important backend modules

```text
backend/app/
├── api/v1/             request-facing application modules
├── auth/               active Supabase Auth adapter/dependencies
├── config/             environment/configuration
├── db/                 database connection/pool
├── features/           domain-specific services
├── gateway/            search cache/limiting layer
├── providers/
│   ├── linkedin/       LinkedIn Playwright provider
│   ├── naukri/         Naukri Playwright provider
│   ├── registry.py     provider registry
│   └── search_engine.py provider orchestration
└── main.py             FastAPI application lifecycle
```

The active authentication implementation uses direct Supabase Auth HTTP calls with connection reuse. Older authentication modules should not be assumed to be active without tracing imports.

---

## 5. Frontend architecture

The frontend is a Next.js App Router application written in React/TypeScript.

Major UI areas:

- authentication
- dashboard
- job search
- pricing
- payment checkout
- payment history
- saved searches
- alert history/test alert
- viewed jobs
- profile/settings/navigation

The frontend uses a centralized typed API client and a same-origin proxy layer. The browser should not contain backend service secrets or internal database credentials.

The frontend documentation intentionally avoids publishing backend API endpoint paths and internal infrastructure details.

---

## 6. Authentication flow

```text
User enters email/password
        |
        v
Frontend auth UI
        |
        v
Backend auth adapter
        |
        v
Supabase Auth
        |
        +--> access token
        +--> refresh token
                 |
                 v
        authenticated frontend session
                 |
                 v
        FastAPI validates identity
                 |
                 v
        application profile + role + plan
```

Supabase Auth is the credential/session source of truth. Application profile and authorization state live in the application's PostgreSQL data.

### Important data distinction

```text
auth.users
   = identity / credentials

public.profiles
   = application profile / role / status / plan
```

Deleting a profile does not necessarily delete the Auth identity. The current backend can provision a missing application profile for a valid authenticated user.

---

## 7. Database architecture

Production data is stored in Supabase PostgreSQL.

Core domains include:

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
alert runs
alert seen-job snapshots
viewed_jobs
```

### Data principles

- User-scoped records are isolated by authenticated user identity.
- RLS is used where applicable.
- Monetary values are stored as INR paise.
- Passwords are never stored in application profile tables.
- Payment webhook events are deduplicated.
- Search quota is consumed before expensive scraping.
- Database schema changes are versioned through Supabase migrations.

### Migration rule

A migration is required for a **schema change**, not simply because rows were deleted.

Examples:

- deleting users/data → no migration by itself;
- adding a column → migration required;
- adding a table → migration required;
- changing a constraint/index/function → migration required.

Before adding a migration, inspect the existing migration history and deployed schema so duplicate migrations are not created.

---

## 8. Current plans and quotas

| Plan | Price | Searches |
|---|---:|---:|
| Free | ₹0 | 50 |
| Starter | ₹299 | 100 |
| Growth | ₹599 | 500 |
| Pro | ₹999 | 1,000 |
| Business | ₹1,499 | 2,000 |

### Quota rules

- Free users receive the Free allocation.
- Normal interactive searches consume quota.
- Alert searches do not consume interactive search quota.
- Super admins are unlimited.
- Quota is consumed before Playwright scraping starts.
- Paid plan activation replaces the previous active quota allocation.
- Existing usage is not falsely added to the new allocation.

This specifically fixed the earlier quota inflation bug:

```text
50 → 100  = 100, not 150
100 → 2000 = 2000, not 2150
```

---

## 9. Payment architecture

Razorpay is used for payment processing and is currently configured in Test Mode during development.

### Payment lifecycle

```text
User selects plan
       |
       v
Backend creates Razorpay order
       |
       v
Razorpay Checkout
       |
       v
Payment completed
       |
       +--> payment ID
       +--> order ID
       +--> signature
                |
                v
        Backend signature verification
                |
                v
        Payment fulfilment transaction
                |
        +-------+--------+----------------+
        |                |                |
        v                v                v
   payment state     plan/quota      subscription
                         |
                         v
                 profile cache invalidated
```

### Security

Only the public checkout key is used by the browser.

Server-side only:

```text
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
```

### Webhooks

The backend handles captured/failed payment events and refund events. Webhook event identifiers are deduplicated so provider retries do not double-fulfil a payment.

### Monthly upgrade

For an active paid monthly plan, upgrading to a higher plan charges only the current-month difference.

Example:

```text
₹299 → ₹599
Pay now: ₹300
Resulting plan: ₹599/month
```

Free → paid charges the full paid-plan amount.

---

## 10. Job search architecture

```text
User presses Search
        |
        v
Frontend search form
        |
        v
Backend search service
        |
        +--> authenticate user
        +--> check/consume quota
        +--> cache lookup
        +--> provider registry
                |
                +--> LinkedIn Playwright
                +--> Naukri Playwright
        |
        v
normalized job response
        |
        v
frontend job cards
```

### Search data

A normalized job can contain:

- platform
- provider job ID
- title
- company
- location
- salary when available
- experience when available
- work mode
- Easy Apply state when available
- job URL
- apply URL
- description
- company logo when available

### Provider limitations

LinkedIn/Naukri searches depend on external sites and browser automation. Provider-side 403s, bot challenges, HTML changes and rate limits cannot be treated as normal database/API latency.

The backend does not attempt to bypass provider access controls.

---

## 11. Saved Search architecture

```text
User creates saved search
        |
        v
PostgreSQL saved-search record
        |
        +--> filters
        +--> alert preference
        +--> schedule
        |
        v
Run Search
        |
        v
normal job-search result shown in UI
```

Saved searches are user-scoped and persisted in the database.

Supported UI operations:

- create
- edit
- delete
- run
- enable/disable alert
- select Daily/Weekly frequency
- manual test alert

When search criteria change, old alert-seen fingerprints are reset so a changed search does not incorrectly suppress new matches.

---

## 12. Alert architecture

### Scheduler

```text
FastAPI lifecycle
      |
      v
scheduler tick
      |
      +--> Daily 09:00 IST
      +--> Weekly Monday 09:00 IST
      |
      v
atomic queue dispatch
```

`FOR UPDATE SKIP LOCKED`-style queue protection prevents duplicate dispatch when multiple workers/processes could inspect the same due work.

### Alert execution

```text
queued run
   ↓
provider search
   ↓
job normalization
   ↓
fingerprint
   ↓
compare with saved-search seen snapshot
   ↓
new jobs only
   ↓
persist count + run status
   ↓
email if new jobs exist
```

### Email

Resend handles delivery.

The backend stores email state and retry information. The email contains useful job details and the external job/apply link.

Required server configuration:

```text
RESEND_API_KEY
RESEND_FROM_EMAIL
```

---

## 13. Manual Test Alert

The manual Test Alert feature was specifically redesigned after DevTools showed repeated calls to alert-status and alert-jobs.

Current intended flow:

```text
Click Test Alert Now
        |
        v
single manual alert execution request
        |
        v
backend performs search
        |
        v
new-job detection
        |
        v
email delivery
        |
        v
request completes
        |
        v
frontend performs one result refresh
```

There is no continuous frontend polling loop.

The UI can then show a message such as:

```text
Found 12 new jobs and sent the alert email.
```

If no new jobs are found, the UI reports zero new jobs without falsely treating a queued/running run as a completed zero result.

---

## 14. Viewed Jobs architecture

Viewed Jobs is intentionally narrower than application tracking.

```text
User opens job card/link
        |
        v
Frontend immediately marks UI state as Viewed
        |
        v
Backend persists viewed record
        |
        v
Viewed count/card badge updates
```

The job-search operation is not rerun just to display Viewed state.

A dedicated Viewed Jobs page provides the user's viewed-job history.

The system does not infer:

```text
Applied
Application submitted
Interview
Rejected
Offer
```

because an external job link does not prove any of those outcomes.

---

## 15. Frontend persistence model

### Backend/database source of truth

- authentication
- profile
- plan
- quota
- payments
- saved searches
- alert history
- viewed jobs

### Local browser persistence

Used only for UI convenience, including saved-search interactive result snapshots and immediate viewed-state fallback where applicable.

Local storage is never proof of payment or application status.

---

## 16. Performance work completed

The project went through a dedicated performance pass after browser DevTools showed 7–25 second non-search calls and duplicate requests.

Completed work includes:

### Backend

- Supabase Auth HTTP client reuse.
- Supabase Auth connection warm-up at startup.
- PostgreSQL pool reuse/warm-up.
- Short-lived authentication verification cache.
- Short-lived authenticated profile cache.
- Payment-triggered profile cache invalidation.
- Saved-search backend caching.
- Viewed-job read optimization.
- Combined alert overview read.
- Exact-search caching.
- Reduced unnecessary Naukri/LinkedIn browser work.
- Concurrent multi-provider searches.

### Frontend

- saved-search in-flight request deduplication
- saved-search short-lived client cache
- mutation-based cache invalidation
- viewed-job in-flight/read deduplication
- no search rerun when a job is marked Viewed
- no repeated manual-alert polling
- one alert-history refresh after manual alert completion

### Important performance expectation

Ordinary authenticated/database APIs are the primary low-latency target. A real LinkedIn/Naukri Playwright search can still take longer because it depends on external provider/browser execution. Performance improvements should reduce unnecessary work rather than claim an artificial fixed latency for external scraping.

---

## 17. Deployment

Current backend deployment:

```text
Mac/local development
      ↓
Git push
      ↓
just-scrapping
      ↓
GitHub Actions
      ↓
Raspberry Pi self-hosted ARM64 runner
      ↓
Supabase migration/deployment validation
      ↓
FastAPI service
      ↓
health/smoke checks
```

Frontend integration branch is `main`.

The frontend may be run locally on the Raspberry Pi during development, while backend deployment is managed by the backend workflow. Production frontend deployment remains a separate deployment concern from the backend service.

---

## 18. Secrets and environment configuration

Secrets must never be committed.

Backend/runtime configuration includes categories such as:

```text
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY / equivalent public Auth key
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_DB_URL / DATABASE_URL
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
RESEND_API_KEY
RESEND_FROM_EMAIL
CORS_ORIGINS
```

The exact current secret values are intentionally not documented here.

GitHub Actions secrets and Raspberry Pi `.env` are the appropriate locations for sensitive values.

---

## 19. CI and testing strategy

The project uses focused validation rather than running every unrelated test for every small change.

Important test categories already covered include:

- Python syntax/import checks
- FastAPI startup checks
- authentication flow
- unauthorized/authorized access
- profile isolation
- quota ordering and exhaustion
- payment verification
- plan upgrades
- prorated upgrades
- webhook idempotency
- refund handling
- saved-search CRUD/isolation
- daily/weekly alert scheduling
- alert job fingerprinting
- email rendering/delivery state
- viewed-job upsert/user isolation
- frontend production build/type checking
- alert polling/request deduplication
- saved-search persistence

---

## 20. Completed project phases

### Backend

- Backend foundation — complete.
- Supabase database — complete.
- Supabase Auth — complete.
- Plans/quota/admin — complete.
- LinkedIn/Naukri search — complete for current provider implementation.
- Razorpay payments — complete for current Test Mode/payment model.
- Saved Searches — complete.
- Job Alerts 5A — scheduling complete.
- Job Alerts 5B — execution/new-job detection complete.
- Job Alerts 5C — Resend email delivery complete.
- Manual Test Alert — complete.
- Viewed Jobs backend — complete.
- Performance hardening — completed for current scope.

### Frontend

- Phase 1 backend integration — complete.
- Phase 2 dashboard/search — complete.
- Phase 3 pricing/payment UI — complete.
- Phase 4 saved-search UI — complete.
- Phase 5A–5E alert/test/history/persistence UI — complete.
- Phase 6 Viewed Jobs UI — complete.
- Duplicate-request and alert-polling performance work — complete.

---

## 21. Product integrity decisions

The project intentionally avoids misleading users.

### We track

- Search usage.
- Saved searches.
- Alert runs.
- New jobs detected by alerts.
- Email delivery state.
- Viewed jobs.
- Payments/plans/quota.

### We do not claim

- that a user applied merely because an external job link was opened;
- that a user submitted an application;
- that an interview occurred;
- that a user was rejected;
- that an offer was received.

This keeps the dashboard and history truthful.

---

## 22. Current completion checkpoint

**Phase 1 is complete for both repositories.**

Backend canonical branch:

```text
just-scrapping
```

Frontend canonical branch:

```text
main
```

The current project state includes the end-to-end foundation from authentication through search, saved searches, alerts, email, payments, viewed jobs, database persistence and performance hardening.

Future work should build on these contracts rather than recreating completed functionality or introducing application-status claims that the system cannot verify.
