from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.features.search_tasks.model import SearchTaskStatus


class CreateSearchTask(BaseModel):
    task_id: str
    platform: str
    job_title: str
    location: str


class SearchTaskResponse(BaseModel):
    id: UUID
    task_id: str
    platform: str
    job_title: str
    location: str
    status: SearchTaskStatus
    progress: int
    result_count: int
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True
    )