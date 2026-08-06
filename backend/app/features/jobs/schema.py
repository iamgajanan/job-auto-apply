from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID


VALID_WORK_MODES = {"remote", "onsite", "hybrid", "any"}


class JobSearchRequest(BaseModel):
    # Provider
    platform: str = "linkedin"

    # Search
    job_title: str
    location: str

    # Filters
    experience: Optional[str] = None
    work_mode: Optional[str] = "any"
    posted_within: Optional[str] = None
    easy_apply: bool = False  # LinkedIn only — ignored by Naukri (no such concept)

    @field_validator("work_mode")
    @classmethod
    def validate_work_mode(cls, v):
        if v is None:
            return "any"
        v = v.strip().lower()
        if v == "":
            return "any"
        if v not in VALID_WORK_MODES:
            raise ValueError(
                f"work_mode must be one of {sorted(VALID_WORK_MODES)}, got {v!r}"
            )
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