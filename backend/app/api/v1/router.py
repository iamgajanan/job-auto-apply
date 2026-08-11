from fastapi import APIRouter

from app.api.v1.jobs import router as jobs_router

router = APIRouter()

router.include_router(jobs_router)
