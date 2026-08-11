from fastapi import APIRouter, Depends, Request

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
    service: JobService = Depends(get_job_service),
):
    client_ip = http_request.client.host
    jobs = service.search_jobs(request, client_ip)
    return {"jobs": jobs}
