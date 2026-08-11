from __future__ import annotations

from typing import Any

import httpx

from app.config.settings import settings


class SupabaseAuthError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class SupabaseAuthService:
    """Server-side adapter around Supabase Auth's HTTP API.

    FastAPI owns the application authorization/profile/quota layer. Supabase
    Auth remains the source of truth for credentials and sessions.

    Direct HTTP is used deliberately here instead of constructing a long-lived
    Supabase Python SDK client for every request. The SDK client initialization
    was failing in the Raspberry Pi runtime even though the same Auth API was
    healthy and reachable, so keeping this adapter HTTP-only removes that
    runtime dependency from the authentication path.
    """

    def _require_config(self) -> None:
        if not settings.SUPABASE_URL or not settings.supabase_auth_key:
            raise SupabaseAuthError("Supabase Auth is not configured", 503)

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
        body: dict[str, Any] = {
            "email": email,
            "password": password,
        }
        if full_name:
            body["data"] = {"full_name": full_name}
        return self._http_request("POST", "/signup", json=body)

    def login(self, email: str, password: str) -> dict[str, Any]:
        return self._http_request(
            "POST",
            "/token?grant_type=password",
            json={"email": email, "password": password},
        )

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self._http_request(
            "POST",
            "/token?grant_type=refresh_token",
            json={"refresh_token": refresh_token},
        )

    def request_password_reset(self, email: str, redirect_to: str | None) -> None:
        body: dict[str, Any] = {"email": email}
        if redirect_to:
            body["redirect_to"] = redirect_to
        self._http_request("POST", "/recover", json=body)

    def update_password(self, access_token: str, password: str) -> dict[str, Any]:
        return self._http_request(
            "PUT",
            "/user",
            access_token=access_token,
            json={"password": password},
        )

    def get_user(self, access_token: str) -> dict[str, Any]:
        return self._http_request("GET", "/user", access_token=access_token)

    def logout(self, access_token: str) -> None:
        self._http_request("POST", "/logout", access_token=access_token)


auth_service = SupabaseAuthService()
