from typing import List, Optional

from pydantic import BaseModel, ConfigDict
from uuid import UUID


class JobSearchRequest(BaseModel):
    # Provider
    platform: str = "linkedin"

    # Search
    job_title: str
    location: str

    # Filters
    experience: Optional[str] = None
    work_mode: Optional[str] = None
    posted_within: Optional[str] = None
    easy_apply: bool = False

    # Future filters
    remote: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: Optional[UUID] = None

    platform: str
    job_id: str

    title: str
    company: str
    location: str

    salary: Optional[str] = None
    experience: Optional[str] = None
    work_mode: Optional[str] = None

    easy_apply: bool = False

    job_url: str
    apply_url: Optional[str] = None

    description: Optional[str] = None
    company_logo: Optional[str] = None

    status: str

    model_config = ConfigDict(from_attributes=True)


class JobSearchResponse(BaseModel):
    jobs: List[JobResponse]

    model_config = ConfigDict(from_attributes=True)