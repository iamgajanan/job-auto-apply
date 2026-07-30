from app.celery_app import celery


@celery.task(
    bind=True,
    name="search.execute",
)
def execute_search(
    self,
    platform: str,
    job_title: str,
    location: str,
):
    """
    Placeholder.

    Next batch will call SearchPipeline.
    """

    print("=" * 60)
    print("Running Search Task")
    print(platform)
    print(job_title)
    print(location)
    print("=" * 60)

    return {
        "status": "QUEUED",
        "task_id": self.request.id,
    }