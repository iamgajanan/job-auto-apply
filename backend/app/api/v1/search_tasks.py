from fastapi import APIRouter, Depends, HTTPException, Request

from app.features.jobs.schema import JobSearchRequest
from app.features.search_tasks.dependencies import get_search_task_service
from app.features.search_tasks.schema import SearchTaskResponse
from app.features.search_tasks.service import SearchTaskService

router = APIRouter(
    prefix="/search-tasks",
    tags=["Search Tasks"],
)


@router.post("")
def create_search_task(
    request: JobSearchRequest,
    http_request: Request,
    service: SearchTaskService = Depends(get_search_task_service),
):
    client_ip = http_request.client.host

    return service.create_search(request, client_ip)


@router.get(
    "/{task_id}",
    response_model=SearchTaskResponse,
)
def get_search_task(
    task_id: str,
    service: SearchTaskService = Depends(get_search_task_service),
):
    task = service.repository.get_by_task_id(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Search task not found")

    return task
