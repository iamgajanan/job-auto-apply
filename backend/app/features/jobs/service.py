from app.common.services.base_service import BaseService


class JobService(BaseService):

    def __init__(self, repository):
        super().__init__(repository)

    def search_jobs(self, request):
        return [
            {
                "platform": request.platform,
                "title": request.job_title,
                "company": "Google",
                "location": request.location,
                "salary": "₹25 LPA",
                "experience": request.experience,
                "easy_apply": True,
                "job_url": "https://linkedin.com/jobs/view/123",
            },
            {
                "platform": request.platform,
                "title": request.job_title,
                "company": "Microsoft",
                "location": request.location,
                "salary": "₹30 LPA",
                "experience": request.experience,
                "easy_apply": False,
                "job_url": "https://linkedin.com/jobs/view/456",
            },
        ]