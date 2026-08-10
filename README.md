# Job Auto Apply

Production-ready AI powered Job Auto Apply System.

## Stack

- Next.js
- FastAPI
- PostgreSQL
- Redis
- Playwright
- Docker

## Local setup

### 1. Create environment file

From the repository root:

```bash
cp .env.example .env
```

The example is configured for the local Docker ports used by this repository: PostgreSQL on `localhost:5433` and Redis on `localhost:6379`.

### 2. Start PostgreSQL and Redis

```bash
docker compose up -d postgres redis
```

Verify both services are healthy:

```bash
docker compose ps
```

### 3. Prepare the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

If Google Chrome is installed locally, the scraper prefers it; otherwise Playwright falls back to its bundled Chromium.

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Start FastAPI

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/api/v1/jobs/health
```

### 6. Search LinkedIn or Naukri

Example request:

```bash
curl -X POST http://localhost:8000/api/v1/jobs/search \
  -H 'Content-Type: application/json' \
  -d '{
    "platform": "naukri",
    "job_title": "react",
    "location": "pune",
    "experience": "5 years",
    "work_mode": "any",
    "posted_within": "day",
    "easy_apply": false
  }'
```

For LinkedIn, use the same payload with `"platform": "linkedin"`. `easy_apply` is applied only by LinkedIn. Naukri enforces the supported experience, work-mode, and posted-within filters against parsed job cards.

### Scraping prerequisites

LinkedIn and Naukri can require a valid browser session, challenge verification, or other upstream access checks. The scraper intentionally stops and reports these conditions instead of bypassing them. Optional `SCRAPER_PROXY_URL` support can be configured in `.env` when needed.
