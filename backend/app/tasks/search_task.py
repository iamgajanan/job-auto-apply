from app.celery_app import celery
from app.db.session import SessionLocal

from app.features.jobs.repository import JobRepository
from app.features.jobs.pipeline import SearchPipeline
from app.features.jobs.schema import JobSearchRequest

from app.features.audit.repository import AuditRepository
from app.features.audit.service import AuditService

from app.features.search_tasks.repository import SearchTaskRepository
from app.features.search_tasks.model import SearchTaskStatus

from app.gateway.cache import SearchCache
from app.gateway.limiter import RateLimiter

from app.providers.search_engine import SearchEngine


@celery.task(
    bind=True,
    name="search.execute",
)
def execute_search(
    self,
    request_data: dict,
    client_ip: str,
):
    """
    Runs a job search through the same SearchPipeline the sync
    /jobs/search endpoint uses, then updates the matching SearchTask
    row (looked up by this Celery task's id) with the outcome.

    NOTE: this task expects its own task_id (self.request.id) to
    already exist as a SearchTask row -- see
    SearchTaskService.create_search, which creates the row BEFORE
    dispatching the task (using apply_async(task_id=...)) specifically
    to avoid a race where this task starts running before the row
    exists.
    """

    db = SessionLocal()

    task_repo = SearchTaskRepository(db)

    try:
        task_repo.update_status(self.request.id, SearchTaskStatus.RUNNING)

        request = JobSearchRequest(**request_data)

        job_repository = JobRepository(db)

        pipeline = SearchPipeline(
            repository=job_repository,
            audit_service=AuditService(AuditRepository(db)),
            cache=SearchCache(),
            limiter=RateLimiter(),
            engine=SearchEngine(),
        )

        jobs = pipeline.execute(request, client_ip)

        task_repo.mark_completed(self.request.id, result_count=len(jobs))

        return {
            "status": "COMPLETED",
            "task_id": self.request.id,
            "result_count": len(jobs),
        }

    except Exception as e:

        task_repo.mark_failed(self.request.id, error=str(e))

        return {
            "status": "FAILED",
            "task_id": self.request.id,
            "error": str(e),
        }

    finally:
        db.close()
