from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as SqlEnum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.db.base import Base


class SearchTaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SearchTask(Base):
    __tablename__ = "search_tasks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    task_id: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    platform: Mapped[str] = mapped_column(String, nullable=False)

    job_title: Mapped[str] = mapped_column(String, nullable=False)

    location: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[SearchTaskStatus] = mapped_column(
        SqlEnum(SearchTaskStatus),
        default=SearchTaskStatus.PENDING,
        nullable=False,
    )

    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    result_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    error: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )