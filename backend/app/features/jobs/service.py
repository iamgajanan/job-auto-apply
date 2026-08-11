class JobService:
    def __init__(self, pipeline):
        self.pipeline = pipeline

    def search_jobs(self, request, client_ip):
        return self.pipeline.execute(request, client_ip)
