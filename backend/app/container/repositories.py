from app.features.audit.repository import AuditRepository
from app.features.jobs.repository import JobRepository
from app.features.search_tasks.repository import SearchTaskRepository


class RepositoryContainer:

    def __init__(self, db):
        self.jobs = JobRepository(db)
        self.audit = AuditRepository(db)
        self.search_tasks = SearchTaskRepository(db)