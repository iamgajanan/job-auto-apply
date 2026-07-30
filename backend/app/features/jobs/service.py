from app.common.services.base_service import BaseService


class JobService(BaseService):

    def __init__(self, repository, pipeline):
        super().__init__(repository)
        self.pipeline = pipeline

    def search_jobs(self, request, client_ip):
        return self.pipeline.execute(request, client_ip)

    def get_jobs(self):
        return self.repository.get_all()