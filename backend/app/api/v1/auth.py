from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.auth.repository import AuthRepository
from app.features.auth.schema import (
    RegisterRequest,
    UserResponse,
)
from app.features.auth.service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(
        AuthRepository(db)
    )

    return service.register(
        full_name=request.full_name,
        email=request.email,
        password=request.password,
    )