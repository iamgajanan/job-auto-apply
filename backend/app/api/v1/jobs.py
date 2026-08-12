from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from uuid import uuid4

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.db.connection import get_engine
from app.features.jobs.dependencies import get_job_service
from app.features.jobs.schema import JobSearchRequest, JobSearchResponse
from app.features.jobs.service import JobService

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)


@router.get("/health")
def health():
    return {"message": "Jobs API Working"}


@router.post(
    "/search",
    response_model=JobSearchResponse,
)
def search_jobs(
    request: JobSearchRequest,
    http_request: Request,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
):
    client_ip = http_request.client.host if http_request.client else "unknown"

    # Super admins are unlimited for testing/operations and are not charged.
    if current_user.profile.role == "super_admin":
        jobs = service.search_jobs(request, client_ip)
        response.headers["X-Searches-Remaining"] = "unlimited"
        return {"jobs": jobs}

    # Consume quota BEFORE running the scraper.
    # Quota is charged on attempt (not on success) because the scraper resource
    # is consumed regardless of whether results are returned. This also prevents
    # a user with 0 quota from triggering an expensive Playwright session.
    request_id = uuid4()
    try:
        with get_engine().begin() as connection:
            quota = connection.execute(
                text(
                    """
                    select *
                    from public.consume_search_quota(
                        :user_id,
                        :platform,
                        :job_title,
                        :location,
                        1,
                        :request_id,
                        cast(:metadata as jsonb)
                    )
                    """
                ),
                {
                    "user_id": current_user.id,
                    "platform": request.platform,
                    "job_title": request.job_title,
                    "location": request.location,
                    "request_id": str(request_id),
                    "metadata": '{"client_ip":"' + client_ip.replace('"', '') + '"}',
                },
            ).mappings().one()
    except SQLAlchemyError as exc:
        if "search quota exceeded" in str(exc).lower():
            raise HTTPException(
                status_code=429,
                detail="Search quota exhausted. Upgrade your plan to continue.",
            ) from exc
        raise

    # Quota successfully consumed — now run the scraper.
    jobs = service.search_jobs(request, client_ip)
    response.headers["X-Searches-Remaining"] = str(quota["remaining_searches"])
    return {"jobs": jobs}
