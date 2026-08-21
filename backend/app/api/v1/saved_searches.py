from fastapi import APIRouter, Depends, Response, status

from app.auth.dependencies import get_current_user
from app.auth.schemas import CurrentUser
from app.features.saved_searches.schemas import (
    CreateSavedSearchRequest,
    SavedSearch,
    SavedSearchAlertJob,
    SavedSearchAlertStatus,
    UpdateSavedSearchRequest,
)
from app.features.saved_searches.service import saved_search_service

router = APIRouter(prefix="/saved-searches", tags=["Saved Searches"])


@router.get("", response_model=dict[str, list[SavedSearch]])
def list_saved_searches(current_user: CurrentUser = Depends(get_current_user)):
    return {"saved_searches": saved_search_service.list(current_user.id)}


@router.get("/{saved_search_id}", response_model=SavedSearch)
def get_saved_search(
    saved_search_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    return saved_search_service.get(current_user.id, saved_search_id)


@router.get("/{saved_search_id}/alert-status", response_model=SavedSearchAlertStatus)
def get_alert_status(
    saved_search_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    return saved_search_service.alert_status(current_user.id, saved_search_id)


@router.get("/{saved_search_id}/alert-jobs", response_model=list[SavedSearchAlertJob])
def get_alert_jobs(
    saved_search_id: str,
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
):
    return saved_search_service.alert_jobs(current_user.id, saved_search_id, limit)


@router.post("/{saved_search_id}/alert-test", status_code=status.HTTP_200_OK)
def queue_test_alert(
    saved_search_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
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
def create_saved_search(
    request: CreateSavedSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    return saved_search_service.create(current_user.id, request)


@router.put("/{saved_search_id}", response_model=SavedSearch)
def update_saved_search(
    saved_search_id: str,
    request: UpdateSavedSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    return saved_search_service.update(current_user.id, saved_search_id, request)


@router.delete("/{saved_search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(
    saved_search_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    saved_search_service.delete(current_user.id, saved_search_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
