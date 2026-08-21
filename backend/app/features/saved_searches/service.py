from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text

from app.db.connection import get_engine
from app.features.saved_searches.schemas import CreateSavedSearchRequest, UpdateSavedSearchRequest

SELECT_FIELDS = """
    id::text,
    name,
    platform,
    job_title,
    location,
    experience,
    work_mode,
    posted_within,
    easy_apply,
    alert_enabled,
    alert_frequency,
    alert_next_run_at,
    alert_last_run_at,
    created_at,
    updated_at
"""


class SavedSearchService:
    def list(self, user_id: str) -> list[dict[str, Any]]:
        with get_engine().connect() as connection:
            rows = connection.execute(
                text(f"select {SELECT_FIELDS} from public.saved_searches where user_id = :user_id order by updated_at desc"),
                {"user_id": user_id},
            ).mappings().all()
        return [dict(row) for row in rows]

    def get(self, user_id: str, saved_search_id: str) -> dict[str, Any]:
        try:
            UUID(saved_search_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Saved search not found") from exc

        with get_engine().connect() as connection:
            row = connection.execute(
                text(f"select {SELECT_FIELDS} from public.saved_searches where id = :id and user_id = :user_id"),
                {"id": saved_search_id, "user_id": user_id},
            ).mappings().one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Saved search not found")
        return dict(row)

    def create(self, user_id: str, request: CreateSavedSearchRequest) -> dict[str, Any]:
        with get_engine().begin() as connection:
            row = connection.execute(
                text(
                    f"""
                    insert into public.saved_searches (
                        user_id, name, platform, job_title, location, experience,
                        work_mode, posted_within, easy_apply, alert_enabled, alert_frequency
                    ) values (
                        :user_id, :name, :platform, :job_title, :location, :experience,
                        :work_mode, :posted_within, :easy_apply, :alert_enabled, :alert_frequency
                    ) returning {SELECT_FIELDS}
                    """
                ),
                {"user_id": user_id, **request.model_dump()},
            ).mappings().one()
        return dict(row)

    def update(self, user_id: str, saved_search_id: str, request: UpdateSavedSearchRequest) -> dict[str, Any]:
        current = self.get(user_id, saved_search_id)
        values = request.model_dump(exclude_unset=True)
        if not values:
            return current

        allowed = {
            "name", "platform", "job_title", "location", "experience", "work_mode",
            "posted_within", "easy_apply", "alert_enabled", "alert_frequency",
        }
        values = {key: value for key, value in values.items() if key in allowed}
        if not values:
            return current

        criteria_fields = {
            "platform", "job_title", "location", "experience",
            "work_mode", "posted_within", "easy_apply",
        }
        criteria_changed = any(
            key in values and values[key] != current.get(key)
            for key in criteria_fields
        )

        if values.get("alert_enabled") is False:
            values["alert_next_run_at"] = None
        elif values.get("alert_enabled") is True and not values.get("alert_frequency"):
            values["alert_frequency"] = current.get("alert_frequency") or "daily"
            values["alert_next_run_at"] = None
        elif values.get("alert_frequency") is not None:
            values["alert_next_run_at"] = None

        if criteria_changed:
            values["alert_next_run_at"] = None
            values["alert_last_run_at"] = None

        params: dict[str, Any] = {"id": saved_search_id, "user_id": user_id}
        assignments: list[str] = []
        for key, value in values.items():
            param = f"value_{key}"
            assignments.append(f"{key} = :{param}")
            params[param] = value

        sql = f"""
            update public.saved_searches
            set {', '.join(assignments)}, updated_at = timezone('utc', now())
            where id = :id and user_id = :user_id
            returning {SELECT_FIELDS}
        """
        try:
            with get_engine().begin() as connection:
                row = connection.execute(text(sql), params).mappings().one_or_none()
                if row and criteria_changed:
                    connection.execute(
                        text(
                            """
                            delete from public.saved_search_alert_jobs
                            where saved_search_id = :saved_search_id and user_id = :user_id
                            """
                        ),
                        {"saved_search_id": saved_search_id, "user_id": user_id},
                    )
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Unable to update saved search.") from exc

        if not row:
            raise HTTPException(status_code=404, detail="Saved search not found")
        return dict(row)

    def delete(self, user_id: str, saved_search_id: str) -> None:
        try:
            UUID(saved_search_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Saved search not found") from exc

        with get_engine().begin() as connection:
            result = connection.execute(
                text("delete from public.saved_searches where id = :id and user_id = :user_id"),
                {"id": saved_search_id, "user_id": user_id},
            )
        if result.rowcount != 1:
            raise HTTPException(status_code=404, detail="Saved search not found")

    def queue_test_alert(self, user_id: str, saved_search_id: str) -> dict[str, Any]:
        saved_search = self.get(user_id, saved_search_id)
        if not saved_search["alert_enabled"]:
            raise HTTPException(status_code=400, detail="Enable job alerts before sending a test alert.")

        now = datetime.now(timezone.utc)
        with get_engine().begin() as connection:
            recent = connection.execute(
                text(
                    """
                    select id::text
                    from public.saved_search_alert_runs
                    where saved_search_id = :saved_search_id
                      and user_id = :user_id
                      and created_at >= timezone('utc', now()) - interval '10 minutes'
                    order by created_at desc
                    limit 1
                    """
                ),
                {"saved_search_id": saved_search_id, "user_id": user_id},
            ).mappings().first()
            if recent:
                raise HTTPException(
                    status_code=429,
                    detail="A test alert was already queued for this saved search in the last 10 minutes.",
                )

            row = connection.execute(
                text(
                    """
                    insert into public.saved_search_alert_runs
                        (saved_search_id, user_id, scheduled_for, status, started_at, result_summary)
                    values
                        (:saved_search_id, :user_id, :scheduled_for, 'running', :started_at, cast(:summary as jsonb))
                    returning id::text, scheduled_for, status, created_at
                    """
                ),
                {
                    "saved_search_id": saved_search_id,
                    "user_id": user_id,
                    "scheduled_for": now,
                    "started_at": now,
                    "summary": '{"trigger":"manual_test"}',
                },
            ).mappings().one()

        from app.features.saved_searches.alert_email import deliver_one_email
        from app.features.saved_searches.alert_executor import process_alert_run

        process_alert_run(row["id"])
        deliver_one_email(row["id"])

        with get_engine().connect() as connection:
            final = connection.execute(
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
                    where r.id = :run_id and r.user_id = :user_id
                    """
                ),
                {"run_id": row["id"], "user_id": user_id},
            ).mappings().one()

        return dict(final)

    def alert_status(self, user_id: str, saved_search_id: str) -> dict[str, Any]:
        saved_search = self.get(user_id, saved_search_id)
        with get_engine().connect() as connection:
            rows = connection.execute(
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
        return {
            "saved_search_id": saved_search_id,
            "alert_enabled": saved_search["alert_enabled"],
            "alert_frequency": saved_search["alert_frequency"],
            "next_run_at": saved_search["alert_next_run_at"],
            "last_run_at": saved_search["alert_last_run_at"],
            "recent_runs": [dict(row) for row in rows],
        }

    def alert_jobs(self, user_id: str, saved_search_id: str, limit: int = 50) -> list[dict[str, Any]]:
        self.get(user_id, saved_search_id)
        safe_limit = min(max(limit, 1), 100)
        with get_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    select id::text, fingerprint, job_data, first_seen_at, last_seen_at
                    from public.saved_search_alert_jobs
                    where saved_search_id = :saved_search_id and user_id = :user_id
                    order by first_seen_at desc
                    limit :limit
                    """
                ),
                {"saved_search_id": saved_search_id, "user_id": user_id, "limit": safe_limit},
            ).mappings().all()
        return [dict(row) for row in rows]


saved_search_service = SavedSearchService()
