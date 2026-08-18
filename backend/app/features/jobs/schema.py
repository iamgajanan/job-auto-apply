from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


VALID_WORK_MODES = {"remote", "onsite", "hybrid", "any"}
VALID_PLATFORMS = {"linkedin", "naukri"}


class JobSearchRequest(BaseModel):
    platform: str = "linkedin"
    job_title: str
    location: str
    experience: Optional[str] = None
    work_mode: Optional[str] = "any"
    posted_within: Optional[str] = None
    easy_apply: bool = False

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v):
        v = v.strip().lower()
        if v not in VALID_PLATFORMS:
            raise ValueError(f"platform must be one of {sorted(VALID_PLATFORMS)}, got {v!r}")
        return v

    @field_validator("work_mode")
    @classmethod
    def validate_work_mode(cls, v):
        if v is None:
            return "any"
        v = v.strip().lower()
        if v == "":
            return "any"
        if v not in VALID_WORK_MODES:
            raise ValueError(f"work_mode must be one of {sorted(VALID_WORK_MODES)}, got {v!r}")
        return v

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


class ViewedJobRequest(JobResponse):
    """The exact job payload returned by search that the user opened."""


class ViewedJob(BaseModel):
    id: str
    platform: str
    job_id: str
    job_data: dict[str, Any]
    viewed_at: datetime
    created_at: datetime
    updated_at: datetime


class ViewedJobsResponse(BaseModel):
    viewed_jobs: list[ViewedJob]
