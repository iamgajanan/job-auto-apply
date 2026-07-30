from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.db.base_model import BaseModel


class SearchLog(BaseModel):
    __tablename__ = "search_logs"

    provider: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    keyword: Mapped[str] = mapped_column(
        String(255),
    )

    location: Mapped[str] = mapped_column(
        String(255),
    )

    client_ip: Mapped[str] = mapped_column(
        String(100),
    )

    request_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    response_source: Mapped[str] = mapped_column(
        String(30),
        default="SCRAPER",
    )

    jobs_found: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    duration_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="SUCCESS",
    )

    error: Mapped[str] = mapped_column(
        Text,
        default="",
    )