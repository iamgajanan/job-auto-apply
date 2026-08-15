# Job Auto Apply

Production-ready AI-powered Job Auto Apply System.

> **Current checkpoint:** `just-scrapping` is the working backend/deployment branch. The project has completed the backend foundation, Supabase Auth, plans/quota, LinkedIn/Naukri search, Razorpay payment integration, Raspberry Pi deployment, Cloudflare exposure, and CI/CD. The next major development phase is the Next.js frontend.

## 1. Project status / checkpoint

### Completed in `just-scrapping`

- FastAPI backend foundation
- Supabase PostgreSQL database and migrations
- Supabase Auth integration
- Signup, login, refresh, logout, `/auth/me`, password reset/update
- Application profiles linked to `auth.users`
- Free-plan signup quota and atomic search-quota consumption
- Plans: Free, Starter, Growth, Pro, Business
- LinkedIn Playwright scraper/provider
- Naukri Playwright scraper/provider
- Search filters and job response schema
- Redis cache/limiter foundation
- Razorpay Test Mode credentials/configuration
- Razorpay order creation
- Payment persistence/history
- Razorpay payment verification/signature validation
- Razorpay webhook endpoint and signature validation
- Webhook idempotency table
- Payment capture -> quota allocation -> profile plan update -> subscription creation
- Refund ledger and refund webhook handling
- Supabase migration CI
- GitHub Actions backend deployment
- Raspberry Pi self-hosted ARM64 runner deployment
- systemd FastAPI service on Raspberry Pi
- Cloudflare Tunnel exposure at `https://jobs`
- Backend/public health checks and authenticated smoke tests
- Razorpay backend smoke tests

### Still to build / finish

- Complete Next.js frontend UI
- Frontend signup/login/session handling
- Dashboard/account/quota UI
- Job-search UI for LinkedIn/Naukri
- Pricing/plans UI
- Razorpay Checkout UI connected to `/payments/orders` and `/payments/verify`
- Payment history UI
- Final browser-level E2E for the complete frontend + payment flow
- Production frontend deployment

**Important:** do not add a database migration or redesign backend APIs just because frontend work starts. First use the existing API contracts. Add backend/database changes only when a real frontend requirement cannot be satisfied by the existing contracts.

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
                +--> jobs
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

FastAPI runtime port on the Pi:

```text
8004
```

Public backend:

```text
https://jobs
```

---

## 3. Repository structure

The important current structure is:

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

### Important active-code note

The active authentication path is the newer `backend/app/auth/` + `backend/app/api/v1/auth.py` implementation, which uses Supabase Auth through HTTP. Do not assume older/legacy authentication code under `backend/app/features/auth/` is the active API path without tracing imports first.

---

## 4. Initial project setup

The project started as the Job Auto Apply backend/frontend repository and was organized around:

- FastAPI for the backend API
- Next.js for the frontend
- Playwright for browser-based job scraping
- PostgreSQL/Supabase for persistent application data
- Redis for cache/rate-limiter support
- Docker for local supporting services
- GitHub for source control and CI/CD

The `just-scrapping` branch became the working branch for the scraping/backend/deployment phase.

---

## 5. PostgreSQL / Supabase setup

### Important clarification

The current production database is **Supabase PostgreSQL**, not a PostgreSQL Docker container on the Raspberry Pi.

`DATABASE_URL` is a server-side PostgreSQL connection string. The Raspberry Pi uses the Supabase Session Pooler connection because the Pi/runtime may be IPv4-only.

The local `docker-compose.yml` currently provides **Redis**. Do not assume a local PostgreSQL container exists just because PostgreSQL is part of the stack.

### Supabase project

`supabase/config.toml` contains the project ID but no secrets.

Secrets stay in GitHub Actions / Pi `.env`; never commit real credentials.

### Database design

Core tables include:

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

Important relationships:

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
   |
   +--> webhook_events
```

Prices are stored as INR paise, not floating-point rupees.

### Current plans

| Code | Name | Price | Search quota |
|---|---|---:|---:|
| free | Free | ₹0 | 50 |
| starter | Starter | ₹299 | 100 |
| growth | Growth | ₹599 | 500 |
| pro | Pro | ₹999 | 1000 |
| business | Business | ₹1499 | 2000 |

`billing_interval` is currently nullable. The current payment model should be treated as credit/plan purchase behavior unless a future requirement explicitly changes it to recurring subscriptions.

### Migrations already created

The current migration history includes:

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

### Do not create duplicate migrations

Before changing DB schema:

1. Check `supabase/migrations/`.
2. Check the deployed Supabase migration history.
3. Confirm the existing API/table/function cannot satisfy the requirement.
4. Only then create a new migration.
5. Push it through the normal deployment workflow.

---

## 6. Authentication implementation

Supabase Auth is the source of truth for credentials and sessions.

FastAPI is responsible for application-level authorization, profile state, plan and quota information.

The active auth adapter is:

```text
backend/app/auth/service.py
```

It calls Supabase Auth HTTP endpoints directly.

This was intentional because the Raspberry Pi runtime had issues with SDK initialization while the same Supabase Auth HTTP API was healthy.

### Authentication API

Base URL:

```text
https://jobs/api/v1
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

Response is an `AuthResponse`. Depending on Supabase email-confirmation settings, `session` may be null and `email_confirmation_required` may be true.

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

Successful response contains:

```json
{
  "user": { "...": "profile" },
  "session": {
    "access_token": "...",
    "refresh_token": "...",
    "token_type": "bearer"
  }
}
```

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

A Supabase Auth user gets an application profile and an initial Free quota allocation through the database trigger/migration logic.

Do not store passwords in `public.profiles`.

---

## 7. Account / plans / quota APIs

### Account

```http
GET /account/me
Authorization: Bearer <access_token>
```

Use this endpoint for the frontend dashboard to display the current profile, plan and search usage.

### Plans

```http
GET /plans
```

The backend currently exposes the five active plans listed above.

### Search quota behavior

`POST /jobs/search` consumes one search unit **before** running the scraper for normal users.

This is intentional: the Playwright/search resource is consumed by the attempt even if the upstream provider returns zero jobs.

If quota is exhausted:

```text
HTTP 429
Search quota exhausted. Upgrade your plan to continue.
```

A successful search response also exposes the remaining quota through the `X-Searches-Remaining` response header.

Super admins are unlimited and are not charged quota.

---

## 8. Job search API

### Endpoint

```http
POST /api/v1/jobs/search
Authorization: Bearer <access_token>
Content-Type: application/json
```

### Request

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

### Response

```json
{
  "jobs": [
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
  ]
}
```

### Search architecture

```text
/jobs/search
   |
   +--> auth validation
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

LinkedIn and Naukri are Playwright/browser providers. They may be affected by login state, bot challenges, upstream HTML changes, rate limits, or provider availability. The scraper should report/block on such conditions rather than attempting unsafe bypasses.

---

## 9. Redis

Redis is part of the local/runtime stack and is used by the search gateway layer for cache/limiting support.

Current Docker Compose service:

```yaml
redis:
  image: redis:7
  port: 6379
```

Persistent Docker volume:

```text
redis_data
```

Local start:

```bash
docker compose up -d redis
```

Verify:

```bash
docker compose ps
redis-cli ping
```

Expected:

```text
PONG
```

---

## 10. Razorpay payment integration

Razorpay is configured in **Test Mode** during development.

### Environment variables

```text
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
```

Never expose `RAZORPAY_KEY_SECRET` or `RAZORPAY_WEBHOOK_SECRET` to the browser.

The browser only needs the public Razorpay Key ID returned by the order API for Checkout initialization.

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

Response:

```json
{
  "order_id": "order_...",
  "amount_inr_paise": 29900,
  "currency": "INR",
  "plan_code": "starter",
  "plan_name": "Starter",
  "search_limit": 100,
  "razorpay_key_id": "rzp_test_..."
}
```

The backend creates the Razorpay order and stores a local `payments` row with status `created`.

### Frontend Checkout flow

The frontend must eventually do:

```text
User clicks Buy
   |
   v
POST /payments/orders
   |
   v
Razorpay Checkout
   |
   +--> successful payment
           |
           +--> razorpay_payment_id
           +--> razorpay_order_id
           +--> razorpay_signature
                     |
                     v
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

The backend verifies the HMAC signature, fetches the payment from Razorpay, checks order ID and amount, and requires Razorpay payment status `captured`.

On successful capture it:

```text
payments.status = captured
        |
        +--> quota allocation for purchased plan
        +--> profiles.plan_code update
        +--> active subscription row
```

### Payment history

```http
GET /api/v1/payments/history
Authorization: Bearer <access_token>
```

Response contains payment ID, plan, provider order/payment IDs, amount, currency, status, refund amount, paid time and creation time.

### Webhook

Razorpay sends webhooks to:

```text
https://jobs/api/v1/payments/webhook
```

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

`webhook_events` stores provider event IDs with a unique `(provider, provider_event_id)` constraint. Duplicate delivery must not grant quota twice.

### Refunds

`payment_refunds` is a separate ledger. Processed refunds update the payment to:

```text
partially_refunded
```

or:

```text
refunded
```

based on the cumulative processed refund amount.

### Payment test status

The backend smoke test proves order creation, payment persistence/history and invalid webhook-signature rejection. A complete browser-level payment E2E should still be re-run whenever the frontend Checkout implementation changes.

---

## 11. GitHub Actions / CI/CD

The deployment workflow is:

```text
.github/workflows/deploy-backend.yml
```

### Trigger

It deploys on pushes to:

```text
just-scrapping
```

or manually through `workflow_dispatch`.

### Deployment sequence

```text
Git push to just-scrapping
        |
        v
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

### GitHub secrets used by deployment

The deployment workflow currently expects secrets for:

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

Never put these values into the README or source files.

### Other workflows

- `database-ci.yml` — migration/database CI
- `test-backend.yml` — backend tests
- `razorpay-smoke.yml` — backend Razorpay smoke tests
- `razorpay-full-e2e.yml` — broader Razorpay E2E work
- `razorpay-final-e2e.yml` — final browser-level Razorpay E2E work
- `razorpay-checkout-diagnostic.yml` — Checkout diagnostics
- `rzp-final.yml` — Razorpay final test workflow

When an E2E workflow fails, do not weaken the test just to get a green check. Diagnose the actual failure, fix it, rerun it, and only then mark the checkpoint complete.

---

## 12. Raspberry Pi self-hosted runner setup

The Raspberry Pi is the production backend host for this branch.

### Required Pi setup

1. Raspberry Pi 5 / ARM64 machine with network access.
2. Git installed.
3. Python and the backend virtual environment installed.
4. Playwright browser dependencies installed.
5. Redis available on port `6379`.
6. Repository cloned to:

```text
/home/iamgajanan/Projects/job-auto-apply
```

7. GitHub Actions self-hosted runner installed in the repository/runner directory.
8. Runner labels must include:

```text
self-hosted
linux
arm64
```

The workflow uses:

```yaml
runs-on: [self-hosted, linux, arm64]
```

### Runner creation concept

In GitHub:

```text
Repository
  -> Settings
  -> Actions
  -> Runners
  -> New self-hosted runner
  -> Linux
  -> ARM64
```

Follow GitHub's generated runner commands on the Pi. Do not copy a runner token into the repository or README.

The runner must be online before a deployment job can execute.

### Repository/branch model

There is **no separate current `pi` branch** in the repository. The current deployment branch is:

```text
just-scrapping
```

The Raspberry Pi runner checks out exactly that branch during deployment:

```bash
git fetch --prune origin just-scrapping
git checkout just-scrapping
git reset --hard origin/just-scrapping
```

If an old document or AI agent refers to a separate `pi` branch, verify the actual GitHub branches before assuming it still exists. The current source of truth is `just-scrapping` + the self-hosted ARM64 runner.

---

## 13. systemd service on Raspberry Pi

The repository contains:

```text
deploy/job-auto-apply.service
```

It runs:

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

Useful commands on the Pi:

```bash
sudo systemctl status job-auto-apply.service
sudo systemctl restart job-auto-apply.service
sudo journalctl -u job-auto-apply.service -n 160 --no-pager
```

The deployment workflow installs/enables/restarts this service automatically.

---

## 14. Cloudflare Tunnel setup

The public backend is exposed through Cloudflare Tunnel.

Current public hostname:

```text
jobs
```

The deployment workflow restarts the existing service:

```text
cloudflared-n8n.service
```

After backend restart it verifies:

```bash
curl --http1.1 https://jobs/
curl --http1.1 https://jobs/api/v1/health/database
```

### Important

Do not create a second tunnel just because the project is named `job-auto-apply`. Reuse the existing Cloudflare configuration unless there is a deliberate infrastructure change.

When the frontend is deployed to a new origin, update `CORS_ORIGINS` in GitHub Secrets and redeploy the backend.

---

## 15. Local development

### Environment

Copy:

```bash
cp .env.example .env
```

Important variables are:

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

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend API client uses:

```text
NEXT_PUBLIC_API_URL + /api/v1
```

Current frontend state at this checkpoint is a minimal Next.js shell/API client, not the finished product UI.

---

## 16. Manual E2E verification checklist

Use this when another AI/tool claims a feature is complete.

### Auth

1. Create a new user with `/auth/signup`.
2. Confirm email if Supabase requires it.
3. Login with `/auth/login`.
4. Save the returned access token.
5. Call `/auth/me` with `Authorization: Bearer <token>`.
6. Call `/account/me` and verify plan/quota.
7. Test logout and verify the old token is rejected.

### LinkedIn

Authenticated request:

```http
POST /api/v1/jobs/search
Authorization: Bearer <token>
```

Use a real job title/location and verify:

```text
HTTP 200
jobs.length > 0
real company/title/location/URL
X-Searches-Remaining decreases
search_usage record exists
```

### Naukri

Repeat the same test with:

```json
{
  "platform": "naukri",
  "job_title": "React Native Developer",
  "location": "Pune",
  "experience": "5 years",
  "work_mode": "any",
  "posted_within": "day",
  "easy_apply": false
}
```

### Payment

1. `GET /plans`.
2. `POST /payments/orders`.
3. Open Razorpay Test Checkout from the frontend.
4. Complete a Test Mode payment.
5. Confirm Razorpay returns:
   - `razorpay_payment_id`
   - `razorpay_order_id`
   - `razorpay_signature`
6. `POST /payments/verify`.
7. Check `/account/me`.
8. Check `/payments/history`.
9. Check Supabase `payments`, `quota_allocations`, and `subscriptions`.
10. Confirm the Razorpay webhook has processed `payment.captured`.
11. Test duplicate webhook delivery does not grant quota twice.
12. Test refund handling separately.

### What counts as payment E2E success

```text
Razorpay order created
       |
       v
Checkout payment succeeds
       |
       v
payment_id + order_id + signature received
       |
       v
/payments/verify = success
       |
       +--> payments.status = captured
       +--> profile.plan_code updated
       +--> quota allocation created
       +--> subscription active
       +--> payment history shows captured
       +--> webhook accepted/idempotent
```

Do not call an order with status `created` an actual successful payment.

---

## 17. Current frontend checkpoint

Backend is intentionally ahead of the frontend.

The frontend should be built against the existing contracts in this order:

```text
1. API client
2. Signup/Login
3. Token/session lifecycle
4. Dashboard/account/quota
5. Job search form
6. LinkedIn/Naukri results
7. Plans/pricing
8. Razorpay Checkout
9. Payment result + account refresh
10. Payment history
11. Error/loading states
12. Responsive UI
13. Production deployment
14. Full browser E2E
```

Do not expose:

```text
SUPABASE_SERVICE_ROLE_KEY
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
SUPABASE_DB_URL/password
```

to the browser.

---

## 18. How to decide whether new backend/DB development is required

Before changing backend/database, ask:

### No backend change needed

If the frontend can satisfy the requirement with an existing endpoint/response, implement it in the frontend.

Examples:

- displaying plan name
- displaying remaining searches
- rendering job results
- displaying payment history
- opening Razorpay Checkout using the public key ID

### Backend change may be required

Only change backend if:

- required data is not exposed by any existing endpoint
- current response contract cannot support the UI
- authorization/security is missing
- payment verification/webhook behavior is incorrect
- a provider integration genuinely needs a fix
- a new server-side business rule is required

### DB migration may be required

Only create a migration if:

- required persistent data has no suitable existing column/table
- existing schema cannot represent the new business rule
- the change cannot safely be derived from existing data

Always inspect current migrations and production migration history first.

---

## 19. Checkpoint history

### Backend foundation checkpoint

The project evolved through authentication, database, quota, provider, deployment and payment work on `just-scrapping`.

### Current checkpoint

Commit:

```text
76f0ebc5a5a495e012d73f9471f905e02d6a527d
```

Message:

```text
checkpoint: payment integration complete with auth plans and job search
```

This checkpoint is the reference point for starting frontend development.

If future work breaks the backend, compare against this checkpoint before changing architecture.

---

## 20. AI/developer handoff rules

Any AI coding agent working on this repository must follow these rules:

1. Work on `just-scrapping` unless explicitly told otherwise.
2. Read this README first.
3. Inspect the actual current branch/files before assuming old context is correct.
4. Do not invent files, endpoints, environment variables or deployment paths.
5. Do not expose or commit secrets.
6. Do not create a DB migration until existing schema/migrations are checked.
7. Do not change authentication architecture without a concrete failure/reason.
8. Do not replace Supabase Auth with a local password/JWT implementation without an explicit architectural decision.
9. Do not replace the real LinkedIn/Naukri providers with mock data to make tests pass.
10. Do not mock Razorpay success in a test that claims to be real E2E.
11. Keep CI assertions meaningful; do not remove assertions just to turn a workflow green.
12. After backend changes, run the relevant tests and verify deployment to the Pi.
13. If a workflow fails, diagnose the actual failure, fix it, rerun it, and report the final status.
14. For frontend work, first consume existing backend contracts before changing backend APIs.
15. Preserve the `76f0ebc5...` checkpoint as the known-good reference for the backend foundation.

---

## 21. Standard AI task workflow

When asking Claude, ChatGPT, Copilot or another coding agent to work on this project, use this process:

```text
1. Read README.md.
2. Confirm branch = just-scrapping.
3. Inspect current git status and recent commits.
4. Inspect the relevant backend/frontend/API/migration files.
5. Reproduce the problem before changing code when possible.
6. Make the smallest correct change.
7. Run focused tests.
8. Run relevant CI/workflow checks.
9. Deploy if the changed component is part of the Pi deployment.
10. Verify the public endpoint when deployment is involved.
11. Only then report success.
```

If the task is a frontend-only change, do not modify backend/database just to make the task easier.

If the task is a backend change, check whether the frontend contract needs updating.

---

## 22. AI handoff prompt

Copy the following prompt when starting work with another AI coding agent:

```text
You are working on my Job Auto Apply project.

Repository:
https://github.com/iamgajanan/job-auto-apply

Working branch:
just-scrapping

FIRST: Read README.md from the just-scrapping branch completely. Treat it as the project handoff document.

CURRENT CHECKPOINT:
76f0ebc5a5a495e012d73f9471f905e02d6a527d
checkpoint: payment integration complete with auth plans and job search

IMPORTANT ARCHITECTURE:
- Next.js frontend is in /frontend.
- FastAPI backend is in /backend.
- Supabase PostgreSQL is the production database.
- Supabase Auth is the source of truth for credentials/sessions.
- Active auth implementation is backend/app/auth + backend/app/api/v1/auth.py.
- Redis is used by the search gateway/cache/limiter layer.
- LinkedIn and Naukri are Playwright providers.
- Razorpay is integrated in Test Mode.
- Raspberry Pi 5 ARM64 hosts the backend.
- Raspberry Pi application path:
  /home/iamgajanan/Projects/job-auto-apply
- FastAPI production service:
  job-auto-apply.service
- FastAPI production port:
  8004
- Public backend:
  https://jobs
- Cloudflare service currently used by deployment:
  cloudflared-n8n.service
- GitHub Actions deploy workflow:
  .github/workflows/deploy-backend.yml
- Deployment runner:
  self-hosted, linux, arm64
- Deployment branch:
  just-scrapping
- There is currently no separate pi branch; the Pi checks out just-scrapping.

COMPLETED BACKEND FEATURES:
- Supabase DB schema + migrations
- Auth signup/login/refresh/logout/me/password reset/update
- Profiles and roles
- Free quota bootstrap
- Atomic search quota consumption
- LinkedIn search provider
- Naukri search provider
- Plans and pricing
- Payment/order persistence
- Razorpay order creation
- Razorpay payment verification
- Razorpay webhook signature validation
- Webhook idempotency
- Payment history
- Refund ledger/webhook handling
- Payment capture -> quota -> plan -> subscription logic
- Pi deployment and Cloudflare exposure
- CI/CD and backend smoke tests

MAIN API CONTRACTS:
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

JOB SEARCH REQUEST SHAPE:
{
  "platform": "linkedin" or "naukri",
  "job_title": "React Native Developer",
  "location": "Pune",
  "experience": "5 years",
  "work_mode": "any",
  "posted_within": "day",
  "easy_apply": false
}

PAYMENT REQUEST SHAPE:
POST /api/v1/payments/orders
{
  "plan_code": "starter"
}

Response contains:
- order_id
- amount_inr_paise
- currency
- plan_code
- plan_name
- search_limit
- razorpay_key_id

After Razorpay Checkout succeeds, the frontend must send:
POST /api/v1/payments/verify
{
  "razorpay_order_id": "...",
  "razorpay_payment_id": "...",
  "razorpay_signature": "..."
}

SECURITY:
Never expose/commit:
- SUPABASE_SERVICE_ROLE_KEY
- DATABASE_URL/password
- RAZORPAY_KEY_SECRET
- RAZORPAY_WEBHOOK_SECRET

DO NOT:
- create unnecessary migrations
- replace real scraper data with mocks
- fake Razorpay success in an E2E test
- weaken CI assertions to make them green
- redesign working auth/deployment architecture without evidence
- assume a historical branch still exists without checking GitHub

WHEN MAKING CHANGES:
1. Inspect current code first.
2. Reproduce the issue.
3. Make the smallest correct change.
4. Run focused tests.
5. Run relevant GitHub Actions workflows.
6. If backend changes, verify Raspberry Pi deployment and public endpoint.
7. If a test fails, diagnose and fix it, then rerun.
8. Only report success after verification.

FOR FRONTEND WORK:
Start by consuming the existing API contracts. Do not modify backend/database unless the UI genuinely requires data or behavior that the current API cannot provide.

FOR DATABASE WORK:
Inspect supabase/migrations and production migration state before creating a new migration.

FOR PAYMENT WORK:
Do not call an order with status 'created' a successful payment. A real successful payment must reach captured/verified state and update payment + quota + plan/subscription as appropriate.

YOUR TASK:
[PASTE THE ACTUAL TASK HERE]

Before finishing, summarize:
- files changed
- why they changed
- tests run
- CI results
- deployment result if applicable
- any remaining limitations
```

---

## 23. Final rule for future development

This README is the project's memory for future AI agents.

When the project moves to the next checkpoint, update this document with:

- new feature completed
- new API contract
- new DB migration
- new environment variable/secret name (never the secret value)
- deployment changes
- workflow changes
- test status
- new checkpoint commit
- known remaining limitations

That way a new AI agent can start from the repository itself instead of relying on old chat history.
