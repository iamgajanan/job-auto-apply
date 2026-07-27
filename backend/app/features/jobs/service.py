from app.common.services.base_service import BaseService


class JobService(BaseService):

    def __init__(self, repository):
        super().__init__(repository)