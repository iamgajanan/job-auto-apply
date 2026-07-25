from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logger import app_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Backend Started")

    yield

    app_logger.info("Backend Stopped")