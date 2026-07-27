from typing import List, Optional

from pydantic import BaseModel
from datetime import datetime

class JobSearchRequest(BaseModel):
    platform: str
    job_title: str
    location: str
    experience: str
    easy_apply: bool = False
    work_mode: str = "Any"


class JobResponse(BaseModel):
    platform: str
    job_id: str
    title: str
    company: str
    location: str

    salary: str
    experience: str

    work_mode: str

    easy_apply: bool

    job_url: str

    apply_url: str

    description: str

    company_logo: str

    posted_at: Optional[datetime] = None

    status: str


class JobSearchResponse(BaseModel):
    jobs: List[JobResponse]