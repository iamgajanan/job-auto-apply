from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["linkedin", "naukri"]
WorkMode = Literal["remote", "onsite", "hybrid", "any"]
AlertFrequency = Literal["daily", "weekly"]
AlertRunStatus = Literal["queued", "running", "completed", "failed", "skipped"]


class SavedSearch(BaseModel):
    id: str
    name: str
    platform: Platform
    job_title: str
    location: str
    experience: str | None
    work_mode: WorkMode | None
    posted_within: str | None
    easy_apply: bool
    alert_enabled: bool
    alert_frequency: AlertFrequency | None
    alert_next_run_at: datetime | None
    alert_last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AlertRun(BaseModel):
    id: str
    saved_search_name: str | None = None
    scheduled_for: datetime
    status: AlertRunStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    new_jobs_count: int = 0
    result_summary: dict | None = None
    error_message: str | None


class SavedSearchAlertJob(BaseModel):
    id: str
    fingerprint: str
    job_data: dict
    first_seen_at: datetime
    last_seen_at: datetime


class SavedSearchAlertStatus(BaseModel):
    saved_search_id: str
    alert_enabled: bool
    alert_frequency: AlertFrequency | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    recent_runs: list[AlertRun]


class CreateSavedSearchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    platform: Platform
    job_title: str = Field(min_length=1, max_length=200)
    location: str = Field(min_length=1, max_length=200)
    experience: str | None = Field(default=None, max_length=100)
    work_mode: WorkMode | None = "any"
    posted_within: str | None = Field(default="day", max_length=50)
    easy_apply: bool = False
    alert_enabled: bool = False
    alert_frequency: AlertFrequency | None = "daily"


class UpdateSavedSearchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    platform: Platform | None = None
    job_title: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    experience: str | None = Field(default=None, max_length=100)
    work_mode: WorkMode | None = None
    posted_within: str | None = Field(default=None, max_length=50)
    easy_apply: bool | None = None
    alert_enabled: bool | None = None
    alert_frequency: AlertFrequency | None = None
