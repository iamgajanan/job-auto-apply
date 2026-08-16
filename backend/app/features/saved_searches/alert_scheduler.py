from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.db.connection import get_engine

LOGGER = logging.getLogger("job_alert_scheduler")
IST = ZoneInfo("Asia/Kolkata")
RUN_AT_HOUR = 9
RUN_AT_MINUTE = 0
POLL_SECONDS = 60


def next_run_at(frequency: str, now: datetime | None = None) -> datetime:
    """Return the next 09:00 IST run for a daily or weekly alert."""
    current = now.astimezone(IST) if now else datetime.now(IST)
    candidate = current.replace(hour=RUN_AT_HOUR, minute=RUN_AT_MINUTE, second=0, microsecond=0)
    if candidate <= current:
        candidate += timedelta(days=1)

    if frequency == "weekly":
        days_until_monday = (7 - candidate.weekday()) % 7
        if days_until_monday:
            candidate += timedelta(days=days_until_monday)
    elif frequency != "daily":
        raise ValueError(f"Unsupported alert frequency: {frequency}")

    return candidate.astimezone(timezone.utc)


def initialize_missing_schedules() -> int:
    """Assign the first run time to enabled alerts created before scheduling existed."""
    with get_engine().begin() as connection:
        rows = connection.execute(
            text(
                """
                select id, alert_frequency
                from public.saved_searches
                where alert_enabled = true
                  and alert_frequency is not null
                  and alert_next_run_at is null
                """
            )
        ).mappings().all()
        for row in rows:
            connection.execute(
                text("update public.saved_searches set alert_next_run_at = :next_run where id = :id"),
                {"id": row["id"], "next_run": next_run_at(row["alert_frequency"])},
            )
    return len(rows)


def dispatch_due_alerts() -> int:
    """Atomically queue due alert runs and advance their next scheduled time."""
    now = datetime.now(timezone.utc)
    dispatched = 0

    with get_engine().begin() as connection:
        rows = connection.execute(
            text(
                """
                select id, user_id, alert_frequency, alert_next_run_at
                from public.saved_searches
                where alert_enabled = true
                  and alert_frequency is not null
                  and alert_next_run_at is not null
                  and alert_next_run_at <= :now
                order by alert_next_run_at
                for update skip locked
                """
            ),
            {"now": now},
        ).mappings().all()

        for row in rows:
            scheduled_for = row["alert_next_run_at"]
            connection.execute(
                text(
                    """
                    insert into public.saved_search_alert_runs
                        (saved_search_id, user_id, scheduled_for, status)
                    values
                        (:saved_search_id, :user_id, :scheduled_for, 'queued')
                    """
                ),
                {
                    "saved_search_id": row["id"],
                    "user_id": row["user_id"],
                    "scheduled_for": scheduled_for,
                },
            )
            connection.execute(
                text(
                    """
                    update public.saved_searches
                    set alert_last_run_at = :run_at,
                        alert_next_run_at = :next_run
                    where id = :id
                    """
                ),
                {
                    "id": row["id"],
                    "run_at": now,
                    "next_run": next_run_at(row["alert_frequency"], now),
                },
            )
            dispatched += 1

    return dispatched


def run_once() -> int:
    initialized = initialize_missing_schedules()
    dispatched = dispatch_due_alerts()
    LOGGER.info("scheduler tick: initialized=%s dispatched=%s", initialized, dispatched)
    return dispatched


def run_forever() -> None:
    LOGGER.info("job alert scheduler started; timezone=Asia/Kolkata run_time=09:00")
    while True:
        try:
            run_once()
        except Exception:
            LOGGER.exception("job alert scheduler tick failed")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
