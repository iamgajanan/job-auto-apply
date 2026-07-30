from sqlalchemy.orm import Session

from app.features.audit.repository import AuditRepository
from app.features.audit.service import AuditService
from app.features.jobs.repository import JobRepository
from app.features.jobs.service import JobService
from app.gateway.cache import SearchCache
from app.gateway.limiter import RateLimiter
from app.providers.search_engine import SearchEngine
from sqlalchemy.orm import Session
from fastapi import Depends
from app.db.session import get_db

def get_job_service(db: Session = Depends(get_db),) -> JobService:
    return JobService(
        repository=JobRepository(db),
        audit_service=AuditService(
            AuditRepository(db),
        ),
        cache=SearchCache(),
        limiter=RateLimiter(),
        engine=SearchEngine(),
    )