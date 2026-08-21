import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logger import app_logger
from app.db.connection import warm_database_pool
from app.features.saved_searches.alert_email import deliver_one_email
from app.features.saved_searches.alert_executor import process_queued_alerts
from app.features.saved_searches.alert_scheduler import run_once


async def _run_alert_worker() -> None:
    while True:
        try:
            # Phase 5A: schedule due saved searches.
            await asyncio.to_thread(run_once)
            # Phase 5B: execute queued searches and record only new jobs.
            await asyncio.to_thread(process_queued_alerts, 5)
            # Phase 5C: deliver queued email notifications.
            for _ in range(5):
                delivered = await asyncio.to_thread(deliver_one_email)
                if not delivered:
                    break
        except asyncio.CancelledError:
            raise
        except Exception:
            app_logger.exception("Saved search alert worker tick failed")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Backend Started")
    try:
        # Pay the managed-Postgres connection setup cost at startup, not on
        # the first authenticated API request.
        await asyncio.to_thread(warm_database_pool)
    except Exception:
        app_logger.exception("Database warm-up failed; requests will retry the pool connection")

    alert_worker_task = asyncio.create_task(_run_alert_worker())

    try:
        yield
    finally:
        alert_worker_task.cancel()
        await asyncio.gather(alert_worker_task, return_exceptions=True)
        app_logger.info("Backend Stopped")
