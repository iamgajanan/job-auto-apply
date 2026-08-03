from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.search_tasks import router as search_tasks_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(jobs_router)
router.include_router(search_tasks_router)