from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.connection import get_engine
from app.features.jobs.schema import JobSearchRequest
from app.providers.search_engine import SearchEngine

LOGGER = logging.getLogger("job_alert_executor")


def _fingerprint(job: dict) -> str:
    platform = str(job.get("platform") or "").strip().lower()
    job_id = str(job.get("job_id") or "").strip()
    job_url = str(job.get("job_url") or "").strip()
    raw = f"{platform}|{job_id or job_url}"
    if raw == "|":
        raw = json.dumps(job, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _job_payload(job) -> dict:
    if hasattr(job, "model_dump"):
        return job.model_dump(mode="json")
    if isinstance(job, dict):
        return job
    return dict(job)


def _claim_queued_run():
    with get_engine().begin() as connection:
        row = connection.execute(
            text(
                """
                select id, saved_search_id, user_id, scheduled_for
                from public.saved_search_alert_runs
                where status = 'queued'
                order by scheduled_for, created_at
                for update skip locked
                limit 1
                """
            )
        ).mappings().first()
        if not row:
            return None
        connection.execute(
            text(
                """
                update public.saved_search_alert_runs
                set status = 'running', started_at = :started_at
                where id = :id
                """
            ),
            {"id": row["id"], "started_at": datetime.now(timezone.utc)},
        )
        return dict(row)


def _load_saved_search(saved_search_id: str, user_id: str):
    with get_engine().begin() as connection:
        row = connection.execute(
            text(
                """
                select id, user_id, platform, job_title, location,
                       experience, work_mode, posted_within, easy_apply,
                       alert_enabled
                from public.saved_searches
                where id = :id and user_id = :user_id
                """
            ),
            {"id": saved_search_id, "user_id": user_id},
        ).mappings().first()
        return dict(row) if row else None


def _record_jobs(saved_search: dict, jobs: list) -> list[dict]:
    new_jobs = []
    now = datetime.now(timezone.utc)
    with get_engine().begin() as connection:
        for raw_job in jobs:
            job = _job_payload(raw_job)
            fingerprint = _fingerprint(job)
            inserted = connection.execute(
                text(
                    """
                    insert into public.saved_search_alert_jobs
                        (saved_search_id, user_id, fingerprint, job_data, first_seen_at, last_seen_at)
                    values
                        (:saved_search_id, :user_id, :fingerprint, cast(:job_data as jsonb), :first_seen_at, :last_seen_at)
                    on conflict (saved_search_id, fingerprint) do nothing
                    returning id
                    """
                ),
                {
                    "saved_search_id": saved_search["id"],
                    "user_id": saved_search["user_id"],
                    "fingerprint": fingerprint,
                    "job_data": json.dumps(job, default=str),
                    "first_seen_at": now,
                    "last_seen_at": now,
                },
            ).first()

            if inserted:
                new_jobs.append(job)
            else:
                connection.execute(
                    text(
                        """
                        update public.saved_search_alert_jobs
                        set last_seen_at = :last_seen_at, job_data = cast(:job_data as jsonb)
                        where saved_search_id = :saved_search_id and fingerprint = :fingerprint
                        """
                    ),
                    {
                        "saved_search_id": saved_search["id"],
                        "fingerprint": fingerprint,
                        "last_seen_at": now,
                        "job_data": json.dumps(job, default=str),
                    },
                )
    return new_jobs


def process_one_queued_alert() -> int:
    run = _claim_queued_run()
    if not run:
        return 0

    run_id = run["id"]
    try:
        saved_search = _load_saved_search(run["saved_search_id"], run["user_id"])
        if not saved_search or not saved_search["alert_enabled"]:
            with get_engine().begin() as connection:
                connection.execute(
                    text(
                        """
                        update public.saved_search_alert_runs
                        set status = 'skipped', completed_at = :completed_at,
                            result_summary = cast(:summary as jsonb)
                        where id = :id
                        """
                    ),
                    {
                        "id": run_id,
                        "completed_at": datetime.now(timezone.utc),
                        "summary": json.dumps({"reason": "alert_disabled_or_deleted"}),
                    },
                )
            return 1

        request = JobSearchRequest(
            platform=saved_search["platform"],
            job_title=saved_search["job_title"],
            location=saved_search["location"],
            experience=saved_search["experience"],
            work_mode=saved_search["work_mode"] or "any",
            posted_within=saved_search["posted_within"],
            easy_apply=saved_search["easy_apply"],
        )

        # Alerts intentionally bypass consume_search_quota: the alert is an
        # automated feature already enabled by the user and must not silently
        # consume interactive search credits.
        jobs = SearchEngine().search(request)
        new_jobs = _record_jobs(saved_search, jobs)
        completed_at = datetime.now(timezone.utc)
        summary = {
            "jobs_found": len(jobs),
            "new_jobs": len(new_jobs),
        }

        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    update public.saved_search_alert_runs
                    set status = 'completed', completed_at = :completed_at,
                        new_jobs_count = :new_jobs_count,
                        result_summary = cast(:summary as jsonb)
                    where id = :id
                    """
                ),
                {
                    "id": run_id,
                    "completed_at": completed_at,
                    "new_jobs_count": len(new_jobs),
                    "summary": json.dumps(summary),
                },
            )
        LOGGER.info(
            "saved search alert completed: search=%s found=%s new=%s",
            saved_search["id"], len(jobs), len(new_jobs),
        )
        return 1
    except Exception as exc:
        LOGGER.exception("saved search alert failed: run=%s", run_id)
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    update public.saved_search_alert_runs
                    set status = 'failed', completed_at = :completed_at, error_message = :error_message
                    where id = :id
                    """
                ),
                {
                    "id": run_id,
                    "completed_at": datetime.now(timezone.utc),
                    "error_message": str(exc)[:2000],
                },
            )
        return 1


def process_queued_alerts(max_runs: int = 5) -> int:
    processed = 0
    for _ in range(max_runs):
        if not process_one_queued_alert():
            break
        processed += 1
    return processed
