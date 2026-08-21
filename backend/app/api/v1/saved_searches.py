from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.features.saved_searches.read_service import saved_search_read_service
from app.features.saved_searches.schemas import (
    CreateSavedSearchRequest,
    SavedSearch,
    SavedSearchAlertJob,
    SavedSearchAlertStatus,
    UpdateSavedSearchRequest,
)
from app.features.saved_searches.service import saved_search_service

router = APIRouter(prefix="/saved-searches", tags=["Saved Searches"])
_SAVED_SEARCH_CACHE_TTL = 10.0
_saved_search_cache: dict[str, tuple[float, list[dict]]] = {}


def _invalidate_saved_search_cache(user_id: str) -> None:
    _saved_search_cache.pop(user_id, None)


@router.get("", response_model=dict[str, list[SavedSearch]])
def list_saved_searches(current_user: CurrentUser = Depends(get_current_user)):
    cached = _saved_search_cache.get(current_user.id)
    if cached and monotonic() - cached[0] < _SAVED_SEARCH_CACHE_TTL:
        return {"saved_searches": cached[1]}
    items = saved_search_service.list(current_user.id)
    _saved_search_cache[current_user.id] = (monotonic(), items)
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
