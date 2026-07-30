from app.features.jobs.service import JobService
from app.features.search_tasks.service import SearchTaskService


class ServiceContainer:

    def __init__(
        self,
        repositories,
        pipelines,
    ):
        self.jobs = JobService(
            repository=repositories.jobs,
            pipeline=pipelines.search,
        )

        self.search_tasks = SearchTaskService(
            repositories.search_tasks,
        )