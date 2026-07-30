from celery import Celery

from app.config.settings import settings

celery = Celery(
    "job_auto_apply",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=False,
    task_track_started=True,
    result_expires=3600,

    # Explicitly import task modules
    imports=(
        "app.tasks.search_task",
    ),
)