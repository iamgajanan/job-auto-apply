from fastapi import APIRouter

from app.api.v1.account import router as account_router
from app.api.v1.admin import router as admin_router
from app.api.v1.admin_payments import router as admin_payments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.payments import router as payments_router
from app.api.v1.plans import router as plans_router
from app.api.v1.saved_searches import router as saved_searches_router

router = APIRouter()

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(account_router)
router.include_router(plans_router)
router.include_router(payments_router)
router.include_router(admin_router)
router.include_router(admin_payments_router)
router.include_router(jobs_router)
router.include_router(saved_searches_router)
