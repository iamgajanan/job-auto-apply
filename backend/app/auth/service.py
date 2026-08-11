from __future__ import annotations

from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.config.settings import settings


class SupabaseAuthError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class SupabaseAuthService:
    """Small server-side adapter around the official Supabase Python Auth client.

    This is intentionally a compatibility layer for the current FastAPI auth
    endpoints. The frontend will later use Supabase Auth directly (Option B),
    while FastAPI remains responsible for authorization, profiles, quotas and
    business rules.
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
        # Supabase Python responses expose user/session as attributes in
        # addition to their serialized representation in different releases.
        for key in ("user", "session"):
            if key not in data and hasattr(response, key):
                data[key] = cls._model_dict(getattr(response, key))
        return data

    @staticmethod
    def _raise_auth_error(exc: Exception) -> None:
        status_code = getattr(exc, "status_code", 400) or 400
        message = str(exc) or "Supabase authentication request failed"
        if hasattr(exc, "message") and getattr(exc, "message"):
            message = str(getattr(exc, "message"))
        raise SupabaseAuthError(message, int(status_code)) from exc

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

    def get_user(self, access_token: str) -> dict[str, Any]:
        client = self._client()
        try:
            response = client.auth.get_user(access_token)
            return self._response_dict(response)
        except Exception as exc:
            self._raise_auth_error(exc)

    def update_password(self, access_token: str, password: str) -> dict[str, Any]:
        client = self._client()
        try:
            # Supabase's user-update API requires an authenticated session.
            # Set the access token with a placeholder refresh token is not safe,
            # so the compatibility endpoint is intentionally left for Option B.
            # The frontend will update passwords through Supabase Auth directly.
            raise SupabaseAuthError(
                "Password updates are handled by Supabase Auth client-side",
                501,
            )
        except SupabaseAuthError:
            raise
        except Exception as exc:
            self._raise_auth_error(exc)

    def logout(self, access_token: str) -> None:
        client = self._client()
        try:
            # Supabase's Python client uses its local session for sign_out.
            # Server-side compatibility logout is therefore a no-op; the
            # client-side Supabase session is authoritative.
            return None
        except Exception as exc:
            self._raise_auth_error(exc)


auth_service = SupabaseAuthService()
