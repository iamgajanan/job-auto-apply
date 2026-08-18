from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.db.connection import get_engine


class ViewedJobService:
    def mark_viewed(self, user_id: str, job: dict[str, Any]) -> dict[str, Any]:
        params = {
            "user_id": user_id,
            "platform": job["platform"],
            "job_id": job["job_id"],
            "job_data": job,
        }
        with get_engine().begin() as connection:
            row = connection.execute(
                text(
                    """
                    insert into public.viewed_jobs
                        (user_id, platform, job_id, job_data, viewed_at, updated_at)
                    values
                        (:user_id, :platform, :job_id, cast(:job_data as jsonb), timezone('utc', now()), timezone('utc', now()))
                    on conflict (user_id, platform, job_id)
                    do update set
                        job_data = excluded.job_data,
                        viewed_at = timezone('utc', now()),
                        updated_at = timezone('utc', now())
                    returning id::text, platform, job_id, job_data, viewed_at, created_at, updated_at
                    """
                ),
                {**params, "job_data": __import__("json").dumps(job)},
            ).mappings().one()
        return dict(row)

    def list_viewed(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 100)
        safe_offset = max(offset, 0)
        with get_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    select id::text, platform, job_id, job_data, viewed_at, created_at, updated_at
                    from public.viewed_jobs
                    where user_id = :user_id
                    order by viewed_at desc
                    limit :limit offset :offset
                    """
                ),
                {"user_id": user_id, "limit": safe_limit, "offset": safe_offset},
            ).mappings().all()
        return [dict(row) for row in rows]

    def get_viewed(self, user_id: str, platform: str, job_id: str) -> dict[str, Any] | None:
        with get_engine().connect() as connection:
            row = connection.execute(
                text(
                    """
                    select id::text, platform, job_id, job_data, viewed_at, created_at, updated_at
                    from public.viewed_jobs
                    where user_id = :user_id and platform = :platform and job_id = :job_id
                    """
                ),
                {"user_id": user_id, "platform": platform, "job_id": job_id},
            ).mappings().one_or_none()
        return dict(row) if row else None


viewed_job_service = ViewedJobService()
