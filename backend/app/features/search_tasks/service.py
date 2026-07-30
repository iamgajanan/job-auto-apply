from app.tasks.search_task import execute_search
from app.features.search_tasks.schema import CreateSearchTask


class SearchTaskService:

    def __init__(self, repository):
        self.repository = repository

    def create_search(self, request, client_ip):

        celery_task = execute_search.delay(
            request.model_dump(),
            client_ip,
        )

        task = self.repository.create(
            CreateSearchTask(
                task_id=celery_task.id,
                platform=request.platform,
                job_title=request.job_title,
                location=request.location,
            )
        )

        return {
            "task_id": task.task_id,
            "status": task.status,
        }