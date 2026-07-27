from app.common.services.base_service import BaseService
from app.providers.search_engine import SearchEngine


class JobService(BaseService):

    def __init__(self, repository):
        super().__init__(repository)

    def search_jobs(self, request):

        engine = SearchEngine()

        jobs = engine.search(request)

        return self.repository.save_many(jobs)

    def get_jobs(self):

        return self.repository.get_all()