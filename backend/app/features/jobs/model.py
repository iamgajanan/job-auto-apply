from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from app.db.base_model import BaseModel


class Job(BaseModel):
    __tablename__ = "jobs"

    platform: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    job_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
    )

    company: Mapped[str] = mapped_column(
        String(255),
    )

    location: Mapped[str] = mapped_column(
        String(255),
    )

    salary: Mapped[str] = mapped_column(
        String(255),
        default="Not Disclosed",
    )

    experience: Mapped[str] = mapped_column(
        String(100),
        default="Not Mentioned",
    )

    work_mode: Mapped[str] = mapped_column(
        String(100),
        default="Unknown",
    )

    easy_apply: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    job_url: Mapped[str] = mapped_column(
        Text,
    )
    apply_url: Mapped[str] = mapped_column(
        Text,
        default="",
    )
    description: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    company_logo: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="NEW",
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "platform": self.platform,
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "salary": self.salary,
            "experience": self.experience,
            "work_mode": self.work_mode,
            "easy_apply": self.easy_apply,
            "job_url": self.job_url,
            "apply_url": self.apply_url,
            "description": self.description,
            "company_logo": self.company_logo,
            "posted_at": (
                self.posted_at.isoformat()
                if self.posted_at
                else None
            ),
            "scraped_at": (
                self.scraped_at.isoformat()
                if self.scraped_at
                else None
            ),
            "status": self.status,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
        }