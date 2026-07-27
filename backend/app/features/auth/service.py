from fastapi import status

from app.common.exceptions.app_exception import AppException
from app.common.security.password import (
    hash_password,
    verify_password,
)
from app.common.security.jwt import create_access_token
from app.features.auth.model import User
from app.features.auth.repository import AuthRepository
from app.common.security.jwt import create_access_token
from app.common.security.password import verify_password
from fastapi import HTTPException
from app.common.services.base_service import BaseService
class AuthService(BaseService):
    def __init__(self, repository: AuthRepository):
        super().__init__(repository)
        # self.repository = repository

    def register(
        self,
        full_name: str,
        email: str,
        password: str,
    ):
        if self.repository.get_by_email(email):
            raise AppException(
                status.HTTP_409_CONFLICT,
                "Email already exists",
            )

        user = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
        )

        return self.repository.create(user)

    def login(
        self,
        email: str,
        password: str,
    ):
        user = self.repository.get_by_email(email)

        if not user:
            raise AppException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid email or password",
            )

        if not verify_password(
            password,
            user.hashed_password,
        ):
            raise AppException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid email or password",
            )

        return create_access_token(str(user.id))
    def login(
        self,
        email: str,
        password: str,
    ):
        user = self.repository.get_by_email(email)

        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        if not verify_password(
            password,
            user.hashed_password,
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        token = create_access_token(
            str(user.id)
        )

        return {
            "access_token": token,
            "token_type": "Bearer",
        }