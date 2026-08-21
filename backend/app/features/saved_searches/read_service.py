from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.db.connection import get_engine
from app.features.saved_searches.service import SELECT_FIELDS


class SavedSearchReadService:
    """Single-query read paths for the alert UI."""

    def alert_overview(self, user_id: str, saved_search_id: str, job_limit: int = 10) -> dict[str, Any]:
        safe_limit = min(max(job_limit, 1), 100)
        with get_engine().connect() as connection:
            search = connection.execute(
                text(
                    f"""
                    select {SELECT_FIELDS}
                    from public.saved_searches
                    where id = :saved_search_id and user_id = :user_id
                    """
                ),
                {"saved_search_id": saved_search_id, "user_id": user_id},
            ).mappings().one_or_none()
            if not search:
                return None

            runs = connection.execute(
                text(
                    """
                    select r.id::text,
                           s.name as saved_search_name,
                           r.scheduled_for,
                           r.status,
                           r.created_at,
                           r.started_at,
                           r.completed_at,
                           r.new_jobs_count,
                           r.result_summary,
                           r.error_message,
                           r.email_status,
                           r.email_error
                    from public.saved_search_alert_runs r
                    join public.saved_searches s
                      on s.id = r.saved_search_id
                     and s.user_id = r.user_id
                    where r.saved_search_id = :saved_search_id
                      and r.user_id = :user_id
                    order by r.created_at desc
                    limit 10
                    """
                ),
                {"saved_search_id": saved_search_id, "user_id": user_id},
            ).mappings().all()

            jobs = connection.execute(
                text(
                    """
                    select id::text, fingerprint, job_data, first_seen_at, last_seen_at
                    from public.saved_search_alert_jobs
                    where saved_search_id = :saved_search_id and user_id = :user_id
                    order by first_seen_at desc
                    limit :job_limit
                    """
                ),
                {"saved_search_id": saved_search_id, "user_id": user_id, "job_limit": safe_limit},
            ).mappings().all()

        return {
            "saved_search_id": saved_search_id,
            "alert_enabled": search["alert_enabled"],
            "alert_frequency": search["alert_frequency"],
            "next_run_at": search["alert_next_run_at"],
            "last_run_at": search["alert_last_run_at"],
            "recent_runs": [dict(row) for row in runs],
            "jobs": [dict(row) for row in jobs],
        }


saved_search_read_service = SavedSearchReadService()
