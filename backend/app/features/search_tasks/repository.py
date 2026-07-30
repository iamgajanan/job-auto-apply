from datetime import datetime

from sqlalchemy.orm import Session

from app.features.search_tasks.model import SearchTask
from app.features.search_tasks.model import SearchTaskStatus
from app.features.search_tasks.schema import CreateSearchTask


class SearchTaskRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, request: CreateSearchTask) -> SearchTask:

        task = SearchTask(
            task_id=request.task_id,
            platform=request.platform,
            job_title=request.job_title,
            location=request.location,
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        return task

    def get_by_task_id(self, task_id: str):

        return (
            self.db.query(SearchTask)
            .filter(SearchTask.task_id == task_id)
            .first()
        )

    def update_status(
        self,
        task_id: str,
        status: SearchTaskStatus,
    ):

        task = self.get_by_task_id(task_id)

        if not task:
            return None

        task.status = status

        self.db.commit()
        self.db.refresh(task)

        return task

    def update_progress(
        self,
        task_id: str,
        progress: int,
    ):

        task = self.get_by_task_id(task_id)

        if not task:
            return None

        task.progress = progress

        self.db.commit()
        self.db.refresh(task)

        return task

    def mark_completed(
        self,
        task_id: str,
        result_count: int,
    ):

        task = self.get_by_task_id(task_id)

        if not task:
            return None

        task.status = SearchTaskStatus.COMPLETED
        task.progress = 100
        task.result_count = result_count
        task.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(task)

        return task

    def mark_failed(
        self,
        task_id: str,
        error: str,
    ):

        task = self.get_by_task_id(task_id)

        if not task:
            return None

        task.status = SearchTaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(task)

        return task