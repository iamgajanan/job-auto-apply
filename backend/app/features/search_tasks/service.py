import uuid

from app.tasks.search_task import execute_search
from app.features.search_tasks.schema import CreateSearchTask


class SearchTaskService:

    def __init__(self, repository):
        self.repository = repository

    def create_search(self, request, client_ip):

        # Generate the task id ourselves and create the DB row BEFORE
        # dispatching to Celery. If we dispatched first (the old
        # behaviour), a fast worker could start executing -- and try to
        # update a SearchTask row -- before that row was ever inserted.
        task_id = str(uuid.uuid4())

        task = self.repository.create(
            CreateSearchTask(
                task_id=task_id,
                platform=request.platform,
                job_title=request.job_title,
                location=request.location,
            )
        )

        execute_search.apply_async(
            args=[request.model_dump(), client_ip],
            task_id=task_id,
        )

        return {
            "task_id": task.task_id,
            "status": task.status,
        }