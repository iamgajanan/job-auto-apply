from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text

from app.db.connection import get_engine
from app.features.saved_searches.schemas import CreateSavedSearchRequest, UpdateSavedSearchRequest


class SavedSearchService:
    def list(self, user_id: str) -> list[dict[str, Any]]:
        with get_engine().connect() as connection:
            rows = connection.execute(
                text(
                    """
                    select
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
                        created_at,
                        updated_at
                    from public.saved_searches
                    where user_id = :user_id
                    order by updated_at desc
                    """
                ),
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
                text(
                    """
                    select
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
                        created_at,
                        updated_at
                    from public.saved_searches
                    where id = :id and user_id = :user_id
                    """
                ),
                {"id": saved_search_id, "user_id": user_id},
            ).mappings().one_or_none()

        if not row:
            raise HTTPException(status_code=404, detail="Saved search not found")
        return dict(row)

    def create(self, user_id: str, request: CreateSavedSearchRequest) -> dict[str, Any]:
        with get_engine().begin() as connection:
            row = connection.execute(
                text(
                    """
                    insert into public.saved_searches (
                        user_id,
                        name,
                        platform,
                        job_title,
                        location,
                        experience,
                        work_mode,
                        posted_within,
                        easy_apply,
                        alert_enabled,
                        alert_frequency
                    ) values (
                        :user_id,
                        :name,
                        :platform,
                        :job_title,
                        :location,
                        :experience,
                        :work_mode,
                        :posted_within,
                        :easy_apply,
                        :alert_enabled,
                        :alert_frequency
                    )
                    returning
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
                        created_at,
                        updated_at
                    """
                ),
                {"user_id": user_id, **request.model_dump()},
            ).mappings().one()
        return dict(row)

    def update(
        self,
        user_id: str,
        saved_search_id: str,
        request: UpdateSavedSearchRequest,
    ) -> dict[str, Any]:
        # Validate the UUID and ownership before attempting the update so that
        # malformed IDs and edits to another user's search consistently return 404.
        self.get(user_id, saved_search_id)
        values = request.model_dump(exclude_unset=True)
        if not values:
            return self.get(user_id, saved_search_id)

        # Keep the update statement explicit instead of dynamically interpolating
        # request field names. This makes the update path deterministic and avoids
        # SQL generation surprises when the request model evolves.
        allowed = {
            "name",
            "platform",
            "job_title",
            "location",
            "experience",
            "work_mode",
            "posted_within",
            "easy_apply",
            "alert_enabled",
            "alert_frequency",
        }
        values = {key: value for key, value in values.items() if key in allowed}
        if not values:
            return self.get(user_id, saved_search_id)

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
            returning
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
                created_at,
                updated_at
        """

        try:
            with get_engine().begin() as connection:
                row = connection.execute(text(sql), params).mappings().one_or_none()
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
                text(
                    "delete from public.saved_searches where id = :id and user_id = :user_id"
                ),
                {"id": saved_search_id, "user_id": user_id},
            )
        if result.rowcount != 1:
            raise HTTPException(status_code=404, detail="Saved search not found")


saved_search_service = SavedSearchService()
