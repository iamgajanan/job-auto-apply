from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db

from .repository import SearchTaskRepository
from .service import SearchTaskService


def get_search_task_service(
    db: Session = Depends(get_db),
):

    repository = SearchTaskRepository(db)

    return SearchTaskService(repository)