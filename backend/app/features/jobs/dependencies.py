from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.features.jobs.repository import JobRepository
from app.features.jobs.service import JobService
from app.features.jobs.pipeline import SearchPipeline

from app.features.audit.repository import AuditRepository
from app.features.audit.service import AuditService

from app.gateway.cache import SearchCache
from app.gateway.limiter import RateLimiter

from app.providers.search_engine import SearchEngine


def get_job_service(
    db: Session = Depends(get_db),
):

    repository = JobRepository(db)

    pipeline = SearchPipeline(
        repository=repository,
        audit_service=AuditService(
            AuditRepository(db)
        ),
        cache=SearchCache(),
        limiter=RateLimiter(),
        engine=SearchEngine(),
    )

    return JobService(
        repository=repository,
        pipeline=pipeline,
    )