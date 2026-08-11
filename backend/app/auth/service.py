from __future__ import annotations

from typing import Any

import httpx

from app.config.settings import settings


class SupabaseAuthError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class SupabaseAuthService:
    """Small server-side adapter around Supabase Auth's HTTP API.

    Passwords never enter our database or application logs. Supabase Auth owns
    credentials, sessions, email confirmation, and password reset flows.
    """

    def _require_config(self) -> None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
            raise SupabaseAuthError("Supabase Auth is not configured", 503)

    @property
    def base_url(self) -> str:
        return settings.SUPABASE_URL.rstrip("/") + "/auth/v1"

    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": settings.SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    @staticmethod
    def _error(response: httpx.Response) -> SupabaseAuthError:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        message = payload.get("msg") or payload.get("message") or payload.get("error_description")
        if not message:
            message = "Supabase authentication request failed"
        return SupabaseAuthError(str(message), response.status_code)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        access_token: str | None = None,
    ) -> dict[str, Any]:
        self._require_config()
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.request(
                    method,
                    f"{self.base_url}/{path.lstrip('/')}",
                    headers=self._headers(access_token),
                    json=json,
                )
        except httpx.HTTPError as exc:
            raise SupabaseAuthError("Supabase Auth is temporarily unavailable", 503) from exc

        if response.status_code >= 400:
            raise self._error(response)

        if not response.content:
            return {}
        return response.json()

    def signup(self, email: str, password: str, full_name: str | None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/signup",
            json={
                "email": email,
                "password": password,
                "data": {"full_name": full_name} if full_name else {},
            },
        )

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/token?grant_type=password",
            json={"email": email, "password": password},
        )

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/token?grant_type=refresh_token",
            json={"refresh_token": refresh_token},
        )

    def get_user(self, access_token: str) -> dict[str, Any]:
        return self._request("GET", "/user", access_token=access_token)

    def logout(self, access_token: str) -> None:
        self._request("POST", "/logout", access_token=access_token)


auth_service = SupabaseAuthService()
