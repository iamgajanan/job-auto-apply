from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.auth.repository import AuthRepository
from app.features.auth.schema import (
    RegisterRequest,
    UserResponse,
)
from app.features.auth.service import AuthService
from app.features.auth.schema import (
    LoginRequest,
    LoginResponse,
)
from app.common.dependencies.auth import get_current_user

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

@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    service = AuthService(
        AuthRepository(db)
    )

    return service.login(
        email=request.email,
        password=request.password,
    )

@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    user=Depends(get_current_user),
):
    return user