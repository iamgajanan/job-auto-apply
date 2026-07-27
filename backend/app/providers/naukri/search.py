class NaukriSearch:

    def search(self, request):
        return [
            {
                "platform": "naukri",
                "job_id": "naukri_001",
                "title": request.job_title,
                "company": "Infosys",
                "location": request.location,
                "salary": "₹18 LPA",
                "experience": request.experience,
                "easy_apply": False,
                "job_url": "https://naukri.com/job/111",
                "apply_url": "https://naukri.com/job/111",
            }
        ]