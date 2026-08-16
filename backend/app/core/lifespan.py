import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logger import app_logger
from app.features.saved_searches.alert_scheduler import run_once


async def _run_alert_scheduler() -> None:
    while True:
        try:
            await asyncio.to_thread(run_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            app_logger.exception("Saved search alert scheduler tick failed")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Backend Started")
    scheduler_task = asyncio.create_task(_run_alert_scheduler())

    try:
        yield
    finally:
        scheduler_task.cancel()
        await asyncio.gather(scheduler_task, return_exceptions=True)
        app_logger.info("Backend Stopped")
