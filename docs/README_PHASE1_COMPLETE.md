# Job Auto Apply Backend — Phase 1 Complete

> **Canonical backend handoff/reference for `just-scrapping`.**
>
> This document is derived from the project's previous real `README.md` checkpoint and preserves its architecture, terminology, contracts, deployment model, database model, payment behavior and AI/developer handoff rules. It is intentionally a backend document; frontend-only implementation details belong in the frontend repository.

## 1. Project status / checkpoint

**Backend Phase 1: COMPLETE**

The `just-scrapping` branch is the working backend/deployment branch.

The backend foundation completed at the checkpoint includes:

- FastAPI backend foundation.
- Supabase PostgreSQL database and migrations.
- Supabase Auth integration.
- Signup, login, refresh, logout, current-user lookup, password reset and password update.
- Application profiles linked to `auth.users`.
- Free-plan signup quota and atomic search-quota consumption.
- Free, Starter, Growth, Pro and Business plans.
- LinkedIn Playwright scraper/provider.
- Naukri Playwright scraper/provider.
- Search filters and normalized job response schema.
- Redis cache/limiter foundation.
- Razorpay Test Mode configuration.
- Razorpay order creation.
- Payment persistence/history.
- Razorpay payment verification/signature validation.
- Razorpay webhook endpoint and signature validation.
- Webhook idempotency table.
- Payment capture → quota allocation → profile plan update → subscription creation.
- Refund ledger and refund webhook handling.
- Supabase migration CI.
- GitHub Actions backend deployment.
- Raspberry Pi self-hosted ARM64 runner deployment.
- systemd FastAPI service on Raspberry Pi.
- Cloudflare Tunnel exposure.
- Backend/public health checks and authenticated smoke tests.
- Razorpay backend smoke tests.

### Important checkpoint boundary

The original backend README described the next major development phase as the Next.js frontend. Therefore this backend Phase 1 document should not claim that later frontend work was part of the original backend checkpoint.

If additional backend features were implemented after that checkpoint, they should be documented from the actual current branch/code and commits rather than inferred from the old README.

### Development rule

Do not add a database migration or redesign backend APIs merely because frontend work starts. First use the existing API contracts. Add backend/database changes only when a real frontend requirement cannot be satisfied by the existing contracts.

---

## 2. High-level architecture

```text
Browser / Next.js frontend
        |
        | HTTPS
        v
Cloudflare Tunnel
        |
        v
Raspberry Pi 5 (ARM64)
        |
        +--> systemd: job-auto-apply.service
        |       |
        |       +--> Uvicorn / FastAPI :8004
        |               |
        |               +--> Supabase Auth HTTP API
        |               +--> Supabase PostgreSQL
        |               +--> Razorpay API
        |               +--> LinkedIn Playwright provider
        |               +--> Naukri Playwright provider
        |               +--> Redis
        |
        +--> cloudflared-n8n.service
                |
                +--> existing public Cloudflare configuration
```

### Runtime locations

Raspberry Pi application directory:

```text
/home/iamgajanan/Projects/job-auto-apply
```

Backend virtual environment:

```text
/home/iamgajanan/Projects/job-auto-apply/backend/.venv
```

FastAPI systemd service:

```text
/etc/systemd/system/job-auto-apply.service
```

FastAPI production port on the Pi:

```text
8004
```

The public backend is exposed through the existing Cloudflare Tunnel configuration.

> The exact public hostname should be taken from the active deployment configuration. Do not invent or hardcode a hostname when the repository/configuration is the source of truth.

---

## 3. Repository structure

Important backend/project structure from the Phase 1 checkpoint:

```text
job-auto-apply/
├── .github/
│   └── workflows/
│       ├── database-ci.yml
│       ├── deploy-backend.yml
│       ├── test-backend.yml
│       ├── razorpay-smoke.yml
│       ├── razorpay-full-e2e.yml
│       ├── razorpay-final-e2e.yml
│       ├── razorpay-checkout-diagnostic.yml
│       └── rzp-final.yml
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── account.py
│   │   │       ├── admin.py
│   │   │       ├── admin_payments.py
│   │   │       ├── health.py
│   │   │       ├── jobs.py
│   │   │       ├── payments.py
│   │   │       └── plans.py
│   │   ├── auth/
│   │   │   ├── dependencies.py
│   │   │   ├── schemas.py
│   │   │   └── service.py
│   │   ├── config/
│   │   ├── db/
│   │   ├── features/
│   │   │   ├── audit/
│   │   │   ├── auth/
│   │   │   ├── jobs/
│   │   │   ├── payments/
│   │   │   └── search_tasks/
│   │   ├── gateway/
│   │   ├── providers/
│   │   │   ├── linkedin/
│   │   │   ├── naukri/
│   │   │   ├── registry.py
│   │   │   └── search_engine.py
│   │   └── main.py
│   └── requirements.txt
│
├── deploy/
│   └── job-auto-apply.service
│
├── frontend/
│   ├── app/
│   ├── lib/api.ts
│   ├── package.json
│   └── ...
│
├── supabase/
│   ├── config.toml
│   └── migrations/
│
├── docker-compose.yml
├── .env.example
├── payment-test-checkout.html
├── razorpay-e2e-runner.js
└── README.md
```

### Active authentication code

The active authentication path is the newer:

```text
backend/app/auth/
backend/app/api/v1/auth.py
```

It uses Supabase Auth through HTTP.

Do not assume older/legacy authentication code under `backend/app/features/auth/` is the active API path without tracing imports first.

---

## 4. Technology stack

| Area | Technology |
|---|---|
| Backend | FastAPI / Python |
| Authentication | Supabase Auth |
| Database | Supabase PostgreSQL |
| Search/browser automation | Playwright |
| Job providers | LinkedIn, Naukri |
| Cache/limiter | Redis |
| Payments | Razorpay Test Mode |
| Deployment | GitHub Actions + Raspberry Pi ARM64 self-hosted runner |
| Process manager | systemd + Uvicorn |
| Public exposure | Cloudflare Tunnel |
| Frontend contract consumer | Next.js |

The project started as a FastAPI + Next.js application using Playwright for browser-based job scraping, Supabase/PostgreSQL for persistence, Redis for cache/rate-limit support, Docker for local supporting services and GitHub for source control/CI/CD.

---

## 5. Supabase PostgreSQL / database

### Production database

The current production database is **Supabase PostgreSQL**.

It is **not** a PostgreSQL Docker container on the Raspberry Pi.

`DATABASE_URL` is a server-side PostgreSQL connection string. The Raspberry Pi uses the Supabase Session Pooler connection because the Pi/runtime may be IPv4-only.

The local `docker-compose.yml` provides Redis; PostgreSQL should not be assumed to be running locally in Docker merely because PostgreSQL is part of the application stack.

### Supabase configuration

`supabase/config.toml` contains the project configuration but no secrets.

Real credentials remain in GitHub Actions secrets and the Raspberry Pi `.env`.

Never commit real credentials.

### Core tables

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
```

### Relationships

```text
auth.users
   |
   +--> profiles
   |
   +--> quota_allocations
   |
   +--> search_usage
   |
   +--> payments
   |
   +--> subscriptions

payments
   |
   +--> payment_refunds
   +--> webhook_events
```

Prices are stored as **INR paise**, not floating-point rupees.

### Current plans

| Code | Name | Price | Search quota |
|---|---|---:|---:|
| `free` | Free | ₹0 | 50 |
| `starter` | Starter | ₹299 | 100 |
| `growth` | Growth | ₹599 | 500 |
| `pro` | Pro | ₹999 | 1,000 |
| `business` | Business | ₹1,499 | 2,000 |

`billing_interval` is nullable in the current model. The Phase 1 payment model should therefore be treated as **credit/plan purchase behavior**, unless a future requirement explicitly changes it to recurring subscriptions.

### Migration history at the checkpoint

```text
202608120001_initial_job_auto_apply_schema
202608120002_auth_quota_admin
202608120003_seed_super_admin_allowlist
202608120004_auth_hardening
202608120005_webhook_events
20260813112130_fix_consume_search_quota_ambiguous_column
202608140001_payment_history_refunds
```

The deployment workflow applies Supabase migrations before deploying the backend.

### Migration discipline

Before changing the database:

1. Check `supabase/migrations/`.
2. Check the deployed Supabase migration history.
3. Confirm the existing API/table/function cannot satisfy the requirement.
4. Only then create a new migration.
5. Push it through the normal deployment workflow.

Deleting application rows does not itself require a migration. Migrations are for schema changes.

---

## 6. Authentication

Supabase Auth is the source of truth for credentials and sessions.

FastAPI owns application-level authorization, profile state, plan and quota information.

Active adapter:

```text
backend/app/auth/service.py
```

It calls the Supabase Auth HTTP API directly.

This implementation was intentional because the Raspberry Pi runtime had SDK initialization issues while the Supabase Auth HTTP API remained healthy.

### Authentication flow

```text
Signup/Login
    ↓
Supabase Auth
    ↓
access + refresh tokens
    ↓
FastAPI authenticated request
    ↓
application profile / role / plan / quota
```

### Authentication contracts

Base API prefix:

```text
/api/v1
```

#### Signup

```http
POST /auth/signup
Content-Type: application/json
```

Example:

```json
{
  "email": "user@example.com",
  "password": "StrongPassword123!",
  "full_name": "Test User"
}
```

Depending on Supabase email-confirmation settings, the response may contain no session and indicate that email confirmation is required.

#### Login

```http
POST /auth/login
Content-Type: application/json
```

```json
{
  "email": "user@example.com",
  "password": "StrongPassword123!"
}
```

Successful authentication returns the application user/profile plus session information containing access and refresh tokens.

#### Authenticated request

```http
Authorization: Bearer <access_token>
```

#### Current user

```http
GET /auth/me
```

#### Refresh

```http
POST /auth/refresh
Content-Type: application/json
```

```json
{
  "refresh_token": "..."
}
```

#### Logout

```http
POST /auth/logout
Authorization: Bearer <access_token>
```

#### Password reset

```http
POST /auth/password-reset
Content-Type: application/json
```

#### Password update

```http
PUT /auth/password
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Signup quota bootstrap

A newly created Supabase Auth user receives an application profile and initial Free quota allocation through the database trigger/migration logic.

Passwords are never stored in `public.profiles`.

---

## 7. Account, plans and quota

### Account

```http
GET /account/me
Authorization: Bearer <access_token>
```

This is the account contract used by the frontend to display the current profile, plan and search usage.

### Plans

```http
GET /plans
```

The endpoint exposes the five active plans listed in the database section.

### Search quota behavior

```text
POST /jobs/search
      ↓
consume one search unit
      ↓
run scraper
```

Normal users consume one search unit **before** running the scraper. This is intentional because the Playwright/search resource is consumed by the attempt even when the provider returns zero jobs.

When quota is exhausted, the API returns:

```text
HTTP 429
Search quota exhausted. Upgrade your plan to continue.
```

A successful search exposes the remaining quota through:

```text
X-Searches-Remaining
```

Super admins are unlimited and are not charged normal search quota.

---

## 8. Job search

### Endpoint

```http
POST /api/v1/jobs/search
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request shape

```json
{
  "platform": "linkedin",
  "job_title": "React Native Developer",
  "location": "Pune",
  "experience": "5 years",
  "work_mode": "any",
  "posted_within": "day",
  "easy_apply": false
}
```

Supported platforms:

```text
linkedin
naukri
```

Supported work modes:

```text
remote
onsite
hybrid
any
```

### Response shape

The normalized response contains a `jobs` collection. A job can contain:

```json
{
  "id": null,
  "platform": "linkedin",
  "job_id": "...",
  "title": "React Native Developer",
  "company": "Example Company",
  "location": "Pune",
  "salary": null,
  "experience": "5 years",
  "work_mode": "hybrid",
  "easy_apply": false,
  "job_url": "https://www.linkedin.com/jobs/view/...",
  "apply_url": "...",
  "description": "...",
  "company_logo": null,
  "status": "..."
}
```

### Search pipeline

```text
/jobs/search
    |
    +--> authentication validation
    |
    +--> consume_search_quota()
    |
    +--> SearchPipeline
            |
            +--> SearchCache
            +--> RateLimiter
            +--> SearchEngine
                    |
                    +--> ProviderRegistry
                            |
                            +--> LinkedInSearch
                            +--> NaukriSearch
```

LinkedIn and Naukri are real Playwright/browser providers. They may be affected by login state, bot challenges, upstream HTML changes, rate limits or provider availability.

The scraper must report/block on those conditions rather than attempting unsafe bypasses or replacing real provider results with mock data.

---

## 9. Redis

Redis is part of the local/runtime stack and is used by the search gateway for cache/limiter support.

Docker Compose service:

```yaml
redis:
  image: redis:7
  port: 6379
```

Persistent Docker volume:

```text
redis_data
```

Local startup:

```bash
docker compose up -d redis
```

Verification:

```bash
docker compose ps
redis-cli ping
```

Expected:

```text
PONG
```

---

## 10. Razorpay payments

Razorpay is configured in **Test Mode** during development.

### Server-side environment variables

```text
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
```

Never expose `RAZORPAY_KEY_SECRET` or `RAZORPAY_WEBHOOK_SECRET` to the browser.

The browser only needs the public Razorpay Key ID returned by the order flow for Checkout initialization.

### Create order

```http
POST /api/v1/payments/orders
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "plan_code": "starter"
}
```

Response contains:

```text
order_id
amount_inr_paise
currency
plan_code
plan_name
search_limit
razorpay_key_id
```

The backend creates the Razorpay order and stores a local `payments` row with status `created`.

### Checkout flow

```text
User selects plan
      ↓
POST /payments/orders
      ↓
Razorpay Checkout
      ↓
Successful payment
      ↓
razorpay_payment_id
razorpay_order_id
razorpay_signature
      ↓
POST /payments/verify
```

### Verify payment

```http
POST /api/v1/payments/verify
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "razorpay_order_id": "order_...",
  "razorpay_payment_id": "pay_...",
  "razorpay_signature": "..."
}
```

The backend:

1. verifies the HMAC signature;
2. fetches the payment from Razorpay;
3. checks order ID and amount;
4. requires Razorpay payment status `captured`;
5. marks the local payment as captured;
6. creates quota allocation for the purchased plan;
7. updates `profiles.plan_code`;
8. creates/updates the active subscription record.

An order with status `created` is **not** a successful payment.

### Payment history

```http
GET /api/v1/payments/history
Authorization: Bearer <access_token>
```

History includes payment ID, plan, provider order/payment IDs, amount, currency, status, refund amount, paid time and creation time.

### Webhook

The backend exposes the Razorpay webhook contract under the payments API.

Configured events:

```text
payment.captured
payment.failed
refund.created
refund.processed
refund.failed
```

The webhook validates `X-Razorpay-Signature` against `RAZORPAY_WEBHOOK_SECRET` using the raw request body.

### Webhook idempotency

`webhook_events` stores provider event IDs with a unique `(provider, provider_event_id)` constraint.

Duplicate provider delivery must not grant quota twice.

### Refunds

`payment_refunds` is a separate refund ledger.

Processed refunds update the payment state to:

```text
partially_refunded
```

or:

```text
refunded
```

based on cumulative processed refund amount.

### Payment verification status

The backend smoke test proves order creation, payment persistence/history and invalid webhook-signature rejection.

A complete browser-level payment E2E should be re-run whenever the frontend Checkout implementation changes.

---

## 11. GitHub Actions / CI/CD

Primary deployment workflow:

```text
.github/workflows/deploy-backend.yml
```

### Trigger

Deployment runs on pushes to:

```text
just-scrapping
```

or through `workflow_dispatch`.

### Deployment sequence

```text
Git push to just-scrapping
        ↓
GitHub Actions
        |
        +--> Supabase migrations (ubuntu-latest)
        |
        +--> Deploy backend (self-hosted linux arm64)
                |
                +--> git fetch/reset just-scrapping
                +--> install Python requirements
                +--> import-check FastAPI
                +--> write managed runtime .env
                +--> install systemd service
                +--> restart FastAPI
                +--> local health check :8004
                +--> restart cloudflared service
                +--> public HTTPS health check
                +--> public DB health check
                +--> auth/plans/security smoke checks
```

### Deployment secrets

The deployment workflow expects secret configuration including:

```text
SUPABASE_DB_URL
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
SUPABASE_ANON_KEY (legacy fallback)
SUPABASE_SERVICE_ROLE_KEY
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
CORS_ORIGINS
CI_TEST_USER_EMAIL
CI_TEST_USER_PASSWORD
```

Only secret **names** belong in documentation. Never put their values in GitHub, README files or source code.

### Other workflows

```text
database-ci.yml              migration/database CI
test-backend.yml             backend tests
razorpay-smoke.yml           backend Razorpay smoke tests
razorpay-full-e2e.yml        broader Razorpay E2E
razorpay-final-e2e.yml       final browser-level Razorpay E2E
razorpay-checkout-diagnostic.yml
rzp-final.yml                Razorpay final test workflow
```

If an E2E workflow fails, diagnose and fix the actual failure. Do not weaken assertions merely to produce a green workflow.

---

## 12. Raspberry Pi deployment

The Raspberry Pi is the production backend host for `just-scrapping`.

### Required runtime

1. Raspberry Pi 5 / ARM64 machine with network access.
2. Git installed.
3. Python and backend virtual environment.
4. Playwright browser dependencies.
5. Redis on port `6379`.
6. Repository checked out at:

```text
/home/iamgajanan/Projects/job-auto-apply
```

7. GitHub Actions self-hosted runner.
8. Runner labels:

```text
self-hosted
linux
arm64
```

The workflow uses:

```yaml
runs-on: [self-hosted, linux, arm64]
```

### Branch model

There is **no separate current `pi` branch**.

The deployment branch is:

```text
just-scrapping
```

The Pi checks out exactly that branch during deployment:

```bash
git fetch --prune origin just-scrapping
git checkout just-scrapping
git reset --hard origin/just-scrapping
```

If an old document refers to a separate `pi` branch, verify the actual GitHub branches before assuming it still exists.

---

## 13. systemd service

Repository service definition:

```text
deploy/job-auto-apply.service
```

It runs Uvicorn with:

```text
/home/iamgajanan/Projects/job-auto-apply/backend/.venv/bin/uvicorn
app.main:app
--host 0.0.0.0
--port 8004
```

Environment file:

```text
/home/iamgajanan/Projects/job-auto-apply/.env
```

Useful Pi commands:

```bash
sudo systemctl status job-auto-apply.service
sudo systemctl restart job-auto-apply.service
sudo journalctl -u job-auto-apply.service -n 160 --no-pager
```

The deployment workflow installs/enables/restarts the service automatically.

---

## 14. Cloudflare Tunnel

The public backend is exposed through the existing Cloudflare Tunnel configuration.

The deployment workflow restarts the existing service:

```text
cloudflared-n8n.service
```

After backend restart, deployment validates the public backend and database health through HTTPS.

### Infrastructure rule

Do not create a second tunnel merely because the project is named Job Auto Apply. Reuse the existing Cloudflare configuration unless there is a deliberate infrastructure change.

When the frontend is deployed to a new origin, update `CORS_ORIGINS` in GitHub Secrets and redeploy the backend.

---

## 15. Local development

### Environment

```bash
cp .env.example .env
```

Important variable names include:

```text
DATABASE_URL
REDIS_URL
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
NEXT_PUBLIC_API_URL
CORS_ORIGINS
SCRAPER_PROXY_URL
OPENAI_API_KEY
OPENROUTER_API_KEY
OLLAMA_BASE_URL
```

Never commit a real `.env`.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Production Pi uses port `8004`; local development commonly uses `8000`.

### Frontend checkpoint

At the original Phase 1 backend checkpoint, the frontend was a minimal Next.js shell/API client and was intentionally scheduled as the next major development phase.

The frontend must consume the existing backend contracts before requesting backend/database redesign.

---

## 16. Backend E2E verification

Use focused verification appropriate to the changed component. Do not replace real integrations with mocks when a test claims to validate the real provider/payment/deployment behavior.

### Authentication

Verify:

1. signup;
2. email confirmation when required;
3. login;
4. authenticated current-user lookup;
5. account/profile and quota lookup;
6. logout;
7. rejection of an invalidated/old token where applicable.

### LinkedIn

Use an authenticated real search and verify:

```text
HTTP 200
jobs.length > 0 when matching jobs exist
real company/title/location/URL data
X-Searches-Remaining decreases
search_usage record exists
```

### Naukri

Repeat with a real Naukri request using a real job title/location.

### Payment

The real payment flow is:

```text
GET /plans
      ↓
POST /payments/orders
      ↓
Razorpay Test Checkout
      ↓
razorpay_payment_id
razorpay_order_id
razorpay_signature
      ↓
POST /payments/verify
      ↓
payment captured
      ↓
profile plan updated
quota allocation created
subscription active
payment history updated
webhook accepted/idempotent
```

Do not call an order with status `created` a successful payment.

Refund behavior should be tested separately when changing refund logic.

---

## 17. API contract reference for frontend integration

The backend contracts available at the Phase 1 checkpoint are:

```text
POST /api/v1/auth/signup
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
POST /api/v1/auth/password-reset
PUT  /api/v1/auth/password
GET  /api/v1/account/me
GET  /api/v1/plans
POST /api/v1/jobs/search
POST /api/v1/payments/orders
POST /api/v1/payments/verify
GET  /api/v1/payments/history
POST /api/v1/payments/webhook
```

The job-search request contract is:

```json
{
  "platform": "linkedin",
  "job_title": "React Native Developer",
  "location": "Pune",
  "experience": "5 years",
  "work_mode": "any",
  "posted_within": "day",
  "easy_apply": false
}
```

The payment order request is:

```json
{
  "plan_code": "starter"
}
```

The payment verification request is:

```json
{
  "razorpay_order_id": "...",
  "razorpay_payment_id": "...",
  "razorpay_signature": "..."
}
```

### Security boundary

The following must never be exposed to browser code:

```text
SUPABASE_SERVICE_ROLE_KEY
DATABASE_URL/password
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
```

---

## 18. How to decide whether backend/database work is required

### No backend change needed

If the frontend can satisfy the requirement using an existing endpoint/response, implement it in the frontend.

Examples:

- displaying plan name;
- displaying remaining searches;
- rendering job results;
- displaying payment history;
- opening Razorpay Checkout using the public key ID.

### Backend change may be required

Change the backend only when:

- required data is not exposed by any existing endpoint;
- the current response contract cannot support the UI;
- authorization/security is missing;
- payment verification/webhook behavior is incorrect;
- a provider integration genuinely needs a fix;
- a new server-side business rule is required.

### DB migration may be required

Create a migration only when:

- required persistent data has no suitable existing column/table;
- existing schema cannot represent the new business rule;
- the change cannot safely be derived from existing data.

Always inspect current migrations and production migration state first.

---

## 19. Known checkpoint reference

The original backend README identified this commit as the Phase 1 reference point:

```text
76f0ebc5a5a495e012d73f9471f905e02d6a527d
```

Commit message:

```text
checkpoint: payment integration complete with auth plans and job search
```

This remains the documented known-good backend foundation reference from the supplied README.

For current work, always inspect the actual `just-scrapping` branch and recent commits before assuming the checkpoint is the latest code state.

---

## 20. AI / developer handoff rules

Any AI coding agent working on this repository must:

1. Work on `just-scrapping` unless explicitly told otherwise.
2. Read the backend README/documentation first.
3. Inspect the actual current branch/files before assuming historical context is correct.
4. Do not invent files, endpoints, environment variables or deployment paths.
5. Never expose or commit secrets.
6. Do not create a database migration until existing schema/migrations are checked.
7. Do not change the authentication architecture without a concrete failure/reason.
8. Do not replace Supabase Auth with a local password/JWT implementation without an explicit architectural decision.
9. Do not replace real LinkedIn/Naukri providers with mock data to make tests pass.
10. Do not mock Razorpay success in a test that claims to be real E2E.
11. Keep CI assertions meaningful; do not remove assertions merely to turn a workflow green.
12. After backend changes, run relevant focused tests and verify Raspberry Pi deployment when applicable.
13. If a workflow fails, diagnose the actual failure, fix it, rerun it and report the final status.
14. For frontend work, consume existing backend contracts before changing backend APIs.
15. Preserve the documented `76f0ebc5...` checkpoint as the known-good historical reference for the backend foundation.

---

## 21. Standard AI task workflow

```text
1. Read README.md / backend Phase 1 documentation.
2. Confirm branch = just-scrapping.
3. Inspect current git status and recent commits.
4. Inspect the relevant backend/API/migration/provider files.
5. Reproduce the problem before changing code when possible.
6. Make the smallest correct change.
7. Run focused tests.
8. Run relevant GitHub Actions/workflow checks.
9. Deploy if the changed component is part of the Pi deployment.
10. Verify the public endpoint when deployment is involved.
11. Only then report success.
```

For a frontend-only change, do not modify backend/database just to make the task easier.

For a backend change, check whether the frontend contract needs updating.

For database work, inspect `supabase/migrations/` and production migration state before creating a migration.

For payment work, never call an order with status `created` a successful payment. A real successful payment must reach captured/verified state and update payment + quota + plan/subscription as appropriate.

---

## 22. Phase 1 completion note

**Backend Phase 1: COMPLETE.**

The supplied original backend README establishes the Phase 1 checkpoint as the completion of the backend foundation, authentication, database/migrations, plans/quota, LinkedIn/Naukri search, Razorpay integration, deployment, Cloudflare exposure and CI/CD/smoke verification.

The next development phase in that original checkpoint was the Next.js frontend. This document preserves that boundary so future agents can distinguish the historical backend foundation from later project work.

### Source-of-truth rule for future updates

When the project reaches another checkpoint, update this document with:

- newly completed backend features;
- new API contracts;
- new DB migrations;
- new environment-variable/secret names, never values;
- deployment changes;
- workflow changes;
- test status;
- new checkpoint commit;
- known remaining limitations.

The backend documentation should always describe the actual repository state rather than relying on old chat history.
