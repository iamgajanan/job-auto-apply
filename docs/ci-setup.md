# CI Setup Guide

## Required GitHub Actions Secrets

Go to: **GitHub → repo → Settings → Secrets and variables → Actions → New repository secret**

### Core secrets (already set)
| Secret | Description |
|--------|-------------|
| `SUPABASE_DB_URL` | Supabase PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL (https://xxx.supabase.co) |
| `SUPABASE_PUBLISHABLE_KEY` | Supabase anon/publishable key |
| `RAZORPAY_KEY_ID` | Razorpay key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay key secret |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay webhook signing secret |
| `CORS_ORIGINS` | Comma-separated allowed CORS origins |

### New secrets to add

| Secret | Description |
|--------|-------------|
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role key (from Supabase dashboard → Settings → API → service_role) |
| `CI_TEST_USER_EMAIL` | Email of a pre-created test user for auth smoke tests |
| `CI_TEST_USER_PASSWORD` | Password of the test user above |

---

## How to create the CI test user (one-time setup)

Because Supabase rate-limits signups per IP, CI uses **login** instead of signup.
You need to create one test user once via the admin API.

### Step 1 — Add SUPABASE_SERVICE_ROLE_KEY secret

1. Go to your Supabase dashboard → **Settings → API**
2. Copy the **service_role** key (keep this secret — never commit it)
3. Add it as `SUPABASE_SERVICE_ROLE_KEY` in GitHub Actions secrets

### Step 2 — Create the CI test user via admin API

Once the backend is deployed with the service-role key, run this from your Pi
(replace with your admin credentials):

```bash
# Login as admin to get a token
TOKEN=$(curl -s -X POST https://jobs.n8npi.live/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"iamgajanan12@gmail.com","password":"YOUR_ADMIN_PASSWORD"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session']['access_token'])")

# Create the CI test user (free plan, email pre-confirmed, no rate limit)
curl -s -X POST https://jobs.n8npi.live/api/v1/admin/users \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "ci-test@jobauto.internal",
    "password": "CiTestPassword123!",
    "full_name": "CI Test User",
    "plan_code": "free"
  }' | python3 -m json.tool
```

### Step 3 — Add CI test user secrets to GitHub

Add these two secrets to GitHub Actions:
- `CI_TEST_USER_EMAIL` = `ci-test@jobauto.internal`
- `CI_TEST_USER_PASSWORD` = `CiTestPassword123!`

After this, every CI deploy will **log in** as this user to run the full
authenticated smoke test — no signups, no rate limits.

---

## How to create the 5 plan test users

Once `SUPABASE_SERVICE_ROLE_KEY` is set and deployed, run:

```bash
python scripts/create_test_users.py \
  --api http://127.0.0.1:8004 \
  --admin-email iamgajanan12@gmail.com \
  --admin-password YOUR_ADMIN_PASSWORD
```

This uses the new `POST /admin/users` endpoint which bypasses Supabase signup
rate limits entirely. Each user gets the correct plan quota automatically.

**Test user credentials:**
| Plan | Email | Password |
|------|-------|----------|
| Free | test.free@jobauto.internal | TestFree123! |
| Starter | test.starter@jobauto.internal | TestStarter123! |
| Growth | test.growth@jobauto.internal | TestGrowth123! |
| Pro | test.pro@jobauto.internal | TestPro123! |
| Business | test.business@jobauto.internal | TestBusiness123! |
