from typing import List, Optional

from pydantic import BaseModel
from datetime import datetime

from typing import Optional

posted_within: Optional[str] = None

class JobSearchRequest(BaseModel):
    platform: str
    job_title: str
    location: str
    experience: str
    easy_apply: bool = False
    work_mode: str = "Any"
    posted_within: Optional[str] = None

class JobResponse(BaseModel):
    platform: str
    job_id: str
    title: str
    company: str
    location: str

    salary: str
    experience: str

    easy_apply: bool 
    work_mode: str 
    posted_within: Optional[str] = None
    job_url: str

    apply_url: str

    description: str

    company_logo: str

    posted_at: Optional[datetime] = None

    status: str


class JobSearchResponse(BaseModel):
    jobs: List[JobResponse]