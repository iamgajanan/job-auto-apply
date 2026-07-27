from typing import List

from pydantic import BaseModel


class JobSearchRequest(BaseModel):
    platform: str
    job_title: str
    location: str
    experience: str
    easy_apply: bool = False
    work_mode: str = "Any"


class JobResponse(BaseModel):
    platform: str
    title: str
    company: str
    location: str
    salary: str
    experience: str
    easy_apply: bool
    job_url: str


class JobSearchResponse(BaseModel):
    jobs: List[JobResponse]