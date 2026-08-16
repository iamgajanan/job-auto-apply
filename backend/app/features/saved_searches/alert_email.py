from __future__ import annotations

import html
import logging
import os
from typing import Any

import httpx
from sqlalchemy import text

from app.db.connection import get_engine

LOGGER = logging.getLogger("job_alert_email")
RESEND_URL = "https://api.resend.com/emails"


def _setting(name: str) -> str:
    return os.getenv(name, "").strip()


def _job_value(job: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = job.get(key)
        if value:
            return str(value)
    return ""


def _render_email(search_name: str, jobs: list[dict[str, Any]]) -> tuple[str, str]:
    subject = f"{len(jobs)} new job{'s' if len(jobs) != 1 else ''} for {search_name}"
    rows = []
    for job in jobs:
        title = html.escape(_job_value(job, "title", "job_title") or "Job opportunity")
        company = html.escape(_job_value(job, "company", "company_name"))
        location = html.escape(_job_value(job, "location"))
        url = _job_value(job, "job_url", "url", "link")
        safe_url = html.escape(url, quote=True)
        meta = " · ".join(value for value in (company, location) if value)
        rows.append(
            f'<li><a href="{safe_url}"><strong>{title}</strong></a>'
            + (f"<br>{meta}" if meta else "")
            + "</li>"
        )
    body = (
        f"<h2>{html.escape(search_name)}</h2>"
        f"<p>We found {len(jobs)} new job{'s' if len(jobs) != 1 else ''} matching your saved search.</p>"
        f"<ul>{''.join(rows)}</ul>"
        "<p>You are receiving this because job alerts are enabled for this saved search.</p>"
    )
    return subject, body


def _load_pending_delivery() -> dict[str, Any] | None:
    with get_engine().begin() as connection:
        delivery = connection.execute(
            text(
                """
                select d.id, d.alert_run_id, d.attempts,
                       r.saved_search_id, r.user_id,
                       s.name as search_name,
                       coalesce(u.email, p.email) as email
                from public.saved_search_alert_email_deliveries d
                join public.saved_search_alert_runs r on r.id = d.alert_run_id
                join public.saved_searches s on s.id = r.saved_search_id
                left join auth.users u on u.id = r.user_id
                left join public.profiles p on p.id = r.user_id
                where d.status = 'queued'
                order by d.created_at
                for update of d skip locked
                limit 1
                """
            )
        ).mappings().first()
        if not delivery:
            return None

        jobs = connection.execute(
            text(
                """
                select job_data
                from public.saved_search_alert_jobs
                where saved_search_id = :saved_search_id
                  and first_seen_at >= (
                      select coalesce(started_at, created_at)
                      from public.saved_search_alert_runs
                      where id = :alert_run_id
                  )
                order by first_seen_at desc
                """
            ),
            {
                "saved_search_id": delivery["saved_search_id"],
                "alert_run_id": delivery["alert_run_id"],
            },
        ).mappings().all()

        connection.execute(
            text(
                "update public.saved_search_alert_email_deliveries "
                "set status = 'sending', attempts = attempts + 1, started_at = timezone('utc', now()) "
                "where id = :id"
            ),
            {"id": delivery["id"]},
        )
        result = dict(delivery)
        result["jobs"] = [row["job_data"] for row in jobs]
        return result


def _send_via_resend(to_email: str, subject: str, html_body: str) -> str:
    api_key = _setting("RESEND_API_KEY")
    from_email = _setting("RESEND_FROM_EMAIL")
    if not api_key or not from_email:
        raise RuntimeError("RESEND_API_KEY and RESEND_FROM_EMAIL are required for job alert emails")
    response = httpx.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"from": from_email, "to": [to_email], "subject": subject, "html": html_body},
        timeout=20,
    )
    response.raise_for_status()
    return str(response.json().get("id") or "")


def deliver_one_email() -> int:
    delivery = _load_pending_delivery()
    if not delivery:
        return 0

    try:
        jobs = delivery["jobs"] or []
        if not delivery["email"] or not jobs:
            raise RuntimeError("Alert email has no recipient or new jobs")
        subject, body = _render_email(delivery["search_name"], jobs)
        provider_id = _send_via_resend(delivery["email"], subject, body)
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    update public.saved_search_alert_email_deliveries
                    set status = 'sent', sent_at = timezone('utc', now()),
                        completed_at = timezone('utc', now()),
                        provider_message_id = :provider_message_id, error_message = null
                    where id = :id
                    """
                ),
                {"id": delivery["id"], "provider_message_id": provider_id},
            )
            connection.execute(
                text(
                    "update public.saved_search_alert_runs set email_status = 'sent', email_error = null where id = :run_id"
                ),
                {"run_id": delivery["alert_run_id"]},
            )
        return 1
    except Exception as exc:
        LOGGER.exception("job alert email delivery failed: delivery=%s", delivery["id"])
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    update public.saved_search_alert_email_deliveries
                    set status = case when attempts >= 3 then 'failed' else 'queued' end,
                        error_message = :error_message,
                        completed_at = case when attempts >= 3 then timezone('utc', now()) else completed_at end
                    where id = :id
                    """
                ),
                {"id": delivery["id"], "error_message": str(exc)[:2000]},
            )
            connection.execute(
                text(
                    "update public.saved_search_alert_runs set email_status = :status, email_error = :error where id = :run_id"
                ),
                {
                    "run_id": delivery["alert_run_id"],
                    "status": "failed" if delivery["attempts"] >= 3 else "queued",
                    "error": str(exc)[:2000],
                },
            )
        return 1
