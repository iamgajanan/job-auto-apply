import json
import logging

import redis
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.config.settings import settings
from app.features.saved_searches.read_service import saved_search_read_service
from app.features.saved_searches.schemas import (
    CreateSavedSearchRequest,
    SavedSearch,
    SavedSearchAlertJob,
    SavedSearchAlertStatus,
    UpdateSavedSearchRequest,
)
from app.features.saved_searches.service import saved_search_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/saved-searches", tags=["Saved Searches"])

_SAVED_SEARCH_CACHE_TTL = 10  # seconds
_redis_pool: redis.ConnectionPool | None = None
_redis_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _redis_pool, _redis_client
    if _redis_client is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        _redis_client = redis.Redis(connection_pool=_redis_pool)
    return _redis_client


def _cache_key(user_id: str) -> str:
    return f"saved_searches:{user_id}"


def _cache_get(user_id: str) -> list | None:
    try:
        raw = _redis().get(_cache_key(user_id))
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("SavedSearch cache GET failed: %s", exc)
        return None


def _cache_put(user_id: str, items: list) -> None:
    try:
        _redis().setex(_cache_key(user_id), _SAVED_SEARCH_CACHE_TTL, json.dumps(items, default=str))
    except Exception as exc:
        logger.warning("SavedSearch cache SET failed: %s", exc)


def _invalidate_saved_search_cache(user_id: str) -> None:
    try:
        _redis().delete(_cache_key(user_id))
    except Exception as exc:
        logger.warning("SavedSearch cache DELETE failed: %s", exc)


@router.get("", response_model=dict[str, list[SavedSearch]])
def list_saved_searches(current_user: CurrentUser = Depends(get_current_user)):
    cached = _cache_get(current_user.id)
    if cached is not None:
        return {"saved_searches": cached}
    items = saved_search_service.list(current_user.id)
    _cache_put(current_user.id, [i if isinstance(i, dict) else i.model_dump(mode="json") for i in items])
    return {"saved_searches": items}


@router.get("/{saved_search_id}", response_model=SavedSearch)
def get_saved_search(saved_search_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return saved_search_service.get(current_user.id, saved_search_id)


@router.get("/{saved_search_id}/alert-overview")
def get_alert_overview(saved_search_id: str, limit: int = 10, current_user: CurrentUser = Depends(get_current_user)):
    overview = saved_search_read_service.alert_overview(current_user.id, saved_search_id, limit)
    if overview is None:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return overview


@router.get("/{saved_search_id}/alert-status", response_model=SavedSearchAlertStatus)
def get_alert_status(saved_search_id: str, current_user: CurrentUser = Depends(get_current_user)):
    return saved_search_service.alert_status(current_user.id, saved_search_id)


@router.get("/{saved_search_id}/alert-jobs", response_model=list[SavedSearchAlertJob])
def get_alert_jobs(saved_search_id: str, limit: int = 50, current_user: CurrentUser = Depends(get_current_user)):
    return saved_search_service.alert_jobs(current_user.id, saved_search_id, limit)


@router.post("/{saved_search_id}/alert-test", status_code=status.HTTP_200_OK)
def queue_test_alert(saved_search_id: str, current_user: CurrentUser = Depends(get_current_user)):
    run = saved_search_service.queue_test_alert(current_user.id, saved_search_id)
    new_jobs = int(run.get("new_jobs_count") or 0)
    email_status = run.get("email_status")
    if run.get("status") == "completed" and new_jobs > 0 and email_status == "sent":
        message = f"Found {new_jobs} new job{'s' if new_jobs != 1 else ''} and sent the alert email."
    elif run.get("status") == "completed" and new_jobs == 0:
        message = "Alert completed. No new jobs were found, so no email was sent."
    elif run.get("status") == "completed" and email_status == "failed":
        message = f"Found {new_jobs} new job{'s' if new_jobs != 1 else ''}, but the alert email could not be sent."
    elif run.get("status") == "failed":
        message = run.get("error_message") or "The alert run failed."
    else:
        message = "Test alert completed."
    return {"message": message, "run": run}


@router.post("", response_model=SavedSearch, status_code=status.HTTP_201_CREATED)
def create_saved_search(request: CreateSavedSearchRequest, current_user: CurrentUser = Depends(get_current_user)):
    result = saved_search_service.create(current_user.id, request)
    _invalidate_saved_search_cache(current_user.id)
    return result


@router.put("/{saved_search_id}", response_model=SavedSearch)
def update_saved_search(saved_search_id: str, request: UpdateSavedSearchRequest, current_user: CurrentUser = Depends(get_current_user)):
    result = saved_search_service.update(current_user.id, saved_search_id, request)
    _invalidate_saved_search_cache(current_user.id)
    return result


@router.delete("/{saved_search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(saved_search_id: str, current_user: CurrentUser = Depends(get_current_user)):
    saved_search_service.delete(current_user.id, saved_search_id)
    _invalidate_saved_search_cache(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
