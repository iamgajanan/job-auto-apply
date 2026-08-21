import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.service import auth_service
from app.core.logger import app_logger
from app.db.connection import warm_database_pool
from app.features.saved_searches.alert_email import deliver_one_email
from app.features.saved_searches.alert_executor import process_queued_alerts
from app.features.saved_searches.alert_scheduler import run_once


async def _run_alert_worker() -> None:
    while True:
        try:
            await asyncio.to_thread(run_once)
            await asyncio.to_thread(process_queued_alerts, 5)
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
        await asyncio.gather(
            asyncio.to_thread(warm_database_pool),
            asyncio.to_thread(auth_service.warm_connection),
        )
    except Exception:
        # One external warm-up failing must not prevent the API from starting.
        app_logger.exception("Startup connection warm-up failed; requests will retry normally")

    alert_worker_task = asyncio.create_task(_run_alert_worker())
    try:
        yield
    finally:
        alert_worker_task.cancel()
        await asyncio.gather(alert_worker_task, return_exceptions=True)
        app_logger.info("Backend Stopped")
