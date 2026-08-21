from __future__ import annotations

from time import monotonic
from typing import Any
import json

from sqlalchemy import text

from app.db.connection import get_engine

_VIEWED_CACHE_TTL = 10.0
_viewed_cache: dict[tuple[str, int, int], tuple[float, list[dict[str, Any]]]] = {}


def _invalidate_user_cache(user_id: str) -> None:
    for key in list(_viewed_cache):
        if key[0] == user_id:
            _viewed_cache.pop(key, None)


class ViewedJobService:
    def mark_viewed(self, user_id: str, job: dict[str, Any]) -> dict[str, Any]:
        params = {
            "user_id": user_id,
            "platform": job["platform"],
            "job_id": job["job_id"],
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
                {**params, "job_data": json.dumps(job)},
            ).mappings().one()
        _invalidate_user_cache(user_id)
        return dict(row)

    def list_viewed(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 100)
        safe_offset = max(offset, 0)
        key = (user_id, safe_limit, safe_offset)
        cached = _viewed_cache.get(key)
        if cached and monotonic() - cached[0] < _VIEWED_CACHE_TTL:
            return cached[1]
        _viewed_cache.pop(key, None)

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
        result = [dict(row) for row in rows]
        if len(_viewed_cache) >= 512:
            _viewed_cache.pop(next(iter(_viewed_cache)))
        _viewed_cache[key] = (monotonic(), result)
        return result

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
