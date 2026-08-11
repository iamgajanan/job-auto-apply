from __future__ import annotations

from typing import Any

import httpx
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.config.settings import settings


class SupabaseAuthError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class SupabaseAuthService:
    """Server-side adapter around Supabase Auth.

    The official Supabase Python client is used for signup/login/refresh/user
    operations. Direct HTTP is retained only for the two operations that accept
    an access token without requiring a locally persisted server session.

    This is a compatibility layer for the current FastAPI auth endpoints. The
    frontend will later use Supabase Auth directly (Option B), while FastAPI
    remains responsible for authorization, profiles, quotas and business rules.
    """

    def _require_config(self) -> None:
        if not settings.SUPABASE_URL or not settings.supabase_auth_key:
            raise SupabaseAuthError("Supabase Auth is not configured", 503)

    def _client(self) -> Client:
        self._require_config()
        try:
            return create_client(
                settings.SUPABASE_URL.rstrip("/"),
                settings.supabase_auth_key,
                options=ClientOptions(
                    auto_refresh_token=False,
                    persist_session=False,
                ),
            )
        except Exception as exc:
            raise SupabaseAuthError("Unable to initialize Supabase Auth", 503) from exc

    @staticmethod
    def _model_dict(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(vars(value))

    @classmethod
    def _response_dict(cls, response: Any) -> dict[str, Any]:
        data = cls._model_dict(response)
        for key in ("user", "session"):
            if key not in data and hasattr(response, key):
                data[key] = cls._model_dict(getattr(response, key))
        return data

    @staticmethod
    def _raise_auth_error(exc: Exception) -> None:
        status_code = getattr(exc, "status_code", 400) or 400
        message = str(exc) or "Supabase authentication request failed"
        if getattr(exc, "message", None):
            message = str(exc.message)
        raise SupabaseAuthError(message, int(status_code)) from exc

    def _http_request(
        self,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_config()
        headers = {
            "apikey": settings.supabase_auth_key,
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        try:
            with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0)) as client:
                response = client.request(
                    method,
                    f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/{path.lstrip('/')}",
                    headers=headers,
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise SupabaseAuthError("Supabase Auth request timed out", 503) from exc
        except httpx.HTTPError as exc:
            raise SupabaseAuthError("Supabase Auth is temporarily unavailable", 503) from exc

        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            message = (
                payload.get("msg")
                or payload.get("message")
                or payload.get("error_description")
                or "Supabase authentication request failed"
            )
            raise SupabaseAuthError(str(message), response.status_code)

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise SupabaseAuthError("Supabase Auth returned invalid JSON", 502) from exc

    def signup(self, email: str, password: str, full_name: str | None) -> dict[str, Any]:
        client = self._client()
        try:
            response = client.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {"data": {"full_name": full_name}} if full_name else {},
                }
            )
            return self._response_dict(response)
        except Exception as exc:
            self._raise_auth_error(exc)

    def login(self, email: str, password: str) -> dict[str, Any]:
        client = self._client()
        try:
            response = client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            return self._response_dict(response)
        except Exception as exc:
            self._raise_auth_error(exc)

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        client = self._client()
        try:
            response = client.auth.refresh_session(refresh_token)
            return self._response_dict(response)
        except Exception as exc:
            self._raise_auth_error(exc)

    def request_password_reset(self, email: str, redirect_to: str | None) -> None:
        client = self._client()
        try:
            options = {"redirect_to": redirect_to} if redirect_to else {}
            client.auth.reset_password_for_email(email, options)
        except Exception as exc:
            self._raise_auth_error(exc)

    def update_password(self, access_token: str, password: str) -> dict[str, Any]:
        return self._http_request(
            "PUT",
            "/user",
            access_token=access_token,
            json={"password": password},
        )

    def get_user(self, access_token: str) -> dict[str, Any]:
        client = self._client()
        try:
            response = client.auth.get_user(access_token)
            return self._response_dict(response)
        except Exception as exc:
            self._raise_auth_error(exc)

    def logout(self, access_token: str) -> None:
        self._http_request("POST", "/logout", access_token=access_token)


auth_service = SupabaseAuthService()
