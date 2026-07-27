from app.common.database.base_repository import BaseRepository
from app.features.jobs.model import Job


class JobRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(
            db=db,
            model=Job,
        )

    def get_by_job_id(self, job_id: str):
        return (
            self.db.query(Job)
            .filter(Job.job_id == job_id)
            .first()
        )