# Architecture Audit — Job Auto Apply Backend

Date: 2026-09-12
Branch: just-scrapping
Scope: read-only architecture/source audit; no product features added.

## Current architecture
- FastAPI application under `backend/app`.
- API composition through `app/api/router.py` and `app/api/v1/router.py`.
- Authentication dependencies/services under `app/auth` and auth endpoints under `app/api/v1/auth.py`.
- Core lifecycle, exceptions, middleware, database, models, schemas, providers, tasks, and payment modules are separated by concern.
- Health endpoints exist; CORS and request logging are registered centrally.
- Repository contains multiple deployment/payment diagnostic workflows that need consolidation review.

## Findings
### Critical
- No critical issue conclusively established from static inspection alone; payment/auth and worker runtime validation is required in subsequent stabilization steps.

### High
1. Multiple payment/Razorpay-specific workflows create CI/deployment complexity and possible duplicated or conflicting validation paths.
2. Authentication, authorization, and user-isolation code spans dependencies, service, and endpoint layers; it requires systematic endpoint-level tests for IDOR and bypass risks.
3. Provider/scraping and background-task behavior is a major reliability boundary; timeout, retry, idempotency, and partial-failure behavior must be verified per provider.
4. Database migration reproducibility and constraint/index coverage require a clean-database validation pass.
5. Production configuration and startup behavior must be validated independently for API, worker, scheduler, Redis, and database dependencies.

### Medium
1. Health functionality appears split between `api/v1/health.py` and `api/v1/endpoints/health.py`; ownership and registration should be clarified.
2. API routers contain broad domains (admin, payments, jobs, saved searches) and need contract tests before internal refactoring.
3. Structured logging and exception redaction should be verified across middleware, tasks, and provider failures.
4. Dependency versions are pinned, but automated vulnerability and stale-dependency checks should be part of CI.

### Low
1. Architecture/runbook documentation should describe request flow, worker flow, provider contracts, and deployment topology.
2. CI workflow naming and responsibility should be simplified after baseline behavior is captured.

## Recommended stabilization order
1. Inventory runtime entrypoints, environment variables, workers, scheduler, and external dependencies.
2. Test auth/user isolation and payment webhook security.
3. Test provider normalization, partial failures, retries, and task idempotency.
4. Validate migrations, indexes, transactions, and clean startup.
5. Consolidate CI checks without removing required coverage.

## Explicit non-goals
No new product features, no major rewrites, and no changes to public API contracts in this audit phase.
