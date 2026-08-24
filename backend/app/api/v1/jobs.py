import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from uuid import uuid4

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.db.connection import get_engine
from app.features.jobs.dependencies import get_job_service
from app.features.jobs.schema import JobSearchRequest, JobSearchResponse, ViewedJob, ViewedJobRequest, ViewedJobsResponse
from app.features.jobs.service import JobService
from app.features.jobs.viewed_service import viewed_job_service
from app.gateway.block_detector import PlatformAccessError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

_REFUND_SQL = text("""
    update public.quota_allocations
    set used_searches = greatest(used_searches - :units, 0),
        updated_at    = timezone('utc', now())
    where id = :allocation_id
""")

_QUOTA_CHECK_SQL = text("""
    select
        qa.id as quota_allocation_id,
        qa.granted_searches,
        qa.used_searches,
        qa.granted_searches - qa.used_searches as remaining_searches
    from public.quota_allocations qa
    where qa.user_id = :user_id
      and qa.starts_at <= timezone('utc', now())
      and (qa.ends_at is null or qa.ends_at > timezone('utc', now()))
      and qa.used_searches < qa.granted_searches
    order by qa.starts_at asc, qa.created_at asc
    limit 1
""")


@router.get("/health")
def health():
    return {"message": "Jobs API Working"}


@router.post("/search", response_model=JobSearchResponse)
def search_jobs(
    request: JobSearchRequest,
    http_request: Request,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
):
    client_ip = http_request.client.host if http_request.client else "unknown"

    # Super-admins bypass quota checks entirely.
    if current_user.profile.role == "super_admin":
        try:
            jobs = service.search_jobs(request, client_ip)
        except PlatformAccessError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        response.headers["X-Searches-Remaining"] = "unlimited"
        return {"jobs": jobs}

    # ── Step 1: verify the user has quota available (read-only, no deduction yet) ──
    with get_engine().connect() as conn:
        quota_row = conn.execute(
            _QUOTA_CHECK_SQL, {"user_id": current_user.id}
        ).mappings().one_or_none()

    if quota_row is None:
        raise HTTPException(
            status_code=429,
            detail="Search quota exhausted. Upgrade your plan to continue.",
        )

    allocation_id = str(quota_row["quota_allocation_id"])
    metadata = json.dumps({"client_ip": client_ip.replace('"', "")})
    request_id = uuid4()

    # ── Step 2: run the scrape BEFORE touching quota ──
    try:
        jobs = service.search_jobs(request, client_ip)
    except PlatformAccessError as exc:
        # Scraper was blocked / hit CAPTCHA — do NOT deduct quota.
        logger.warning("Scraper blocked for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Any other scraper error — quota is NOT deducted.
        logger.exception("Scraper error for user %s", current_user.id)
        raise HTTPException(status_code=503, detail="Job search failed. Your quota was not consumed.") from exc

    # ── Step 3: scrape succeeded — now deduct quota and log usage ──
    try:
        with get_engine().begin() as conn:
            quota = conn.execute(text("""
                select * from public.consume_search_quota(
                    :user_id, :platform, :job_title, :location, 1, :request_id,
                    cast(:metadata as jsonb)
                )
            """), {
                "user_id": current_user.id,
                "platform": request.platform,
                "job_title": request.job_title,
                "location": request.location,
                "request_id": str(request_id),
                "metadata": metadata,
            }).mappings().one()
    except SQLAlchemyError as exc:
        # Quota was not deducted (transaction rolled back). Return results anyway —
        # better to give the user their results than lose them due to a DB hiccup.
        # Log loudly so ops can investigate.
        logger.error(
            "Quota deduction failed for user %s (allocation %s) after successful scrape: %s",
            current_user.id, allocation_id, exc,
        )
        response.headers["X-Searches-Remaining"] = str(quota_row["remaining_searches"])
        return {"jobs": jobs}

    response.headers["X-Searches-Remaining"] = str(quota["remaining_searches"])
    return {"jobs": jobs}

@router.post("/viewed", response_model=ViewedJob)
def mark_job_viewed(request: ViewedJobRequest, current_user: CurrentUser = Depends(get_current_user)):
    return viewed_job_service.mark_viewed(current_user.id, request.model_dump(mode="json"))

@router.get("/viewed", response_model=ViewedJobsResponse)
def list_viewed_jobs(limit: int = 50, offset: int = 0, current_user: CurrentUser = Depends(get_current_user)):
    return {"viewed_jobs": viewed_job_service.list_viewed(current_user.id, limit, offset)}

@router.get("/viewed/{platform}/{job_id}", response_model=ViewedJob | None)
def get_viewed_job(platform: str, job_id: str, current_user: CurrentUser = Depends(get_current_user)):
    if platform not in {"linkedin", "naukri"}:
        raise HTTPException(status_code=400, detail="Unsupported job platform.")
    return viewed_job_service.get_viewed(current_user.id, platform, job_id)
