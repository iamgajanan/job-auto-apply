class LinkedInSearch:

    def search(self, request):
        return [
            {
                "platform": "linkedin",
                "job_id": "linkedin_001",
                "title": request.job_title,
                "company": "Google",
                "location": request.location,
                "salary": "₹25 LPA",
                "experience": request.experience,
                "easy_apply": True,
                "job_url": "https://linkedin.com/jobs/view/111",
                "apply_url": "https://linkedin.com/jobs/view/111",
            },
            {
                "platform": "linkedin",
                "job_id": "linkedin_002",
                "title": request.job_title,
                "company": "Microsoft",
                "location": request.location,
                "salary": "₹30 LPA",
                "experience": request.experience,
                "easy_apply": False,
                "job_url": "https://linkedin.com/jobs/view/222",
                "apply_url": "https://linkedin.com/jobs/view/222",
            },
        ]