from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.jobs.repository import JobRepository
from app.features.jobs.schema import (
    JobSearchRequest,
    JobSearchResponse,
)
from app.features.jobs.service import JobService

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)


@router.get("/health")
def health():
    return {
        "message": "Jobs API Working",
    }


@router.post(
    "/search",
    response_model=JobSearchResponse,
)
def search_jobs(
    request: JobSearchRequest,
    db: Session = Depends(get_db),
):
    service = JobService(
        JobRepository(db),
    )

    jobs = service.search_jobs(request)

    return {
        "jobs": jobs,
    }


@router.get("")
def get_jobs(
    db: Session = Depends(get_db),
):
    service = JobService(
        JobRepository(db),
    )

    return service.get_jobs()