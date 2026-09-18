"""Streamlit-safe HTTP client for the FastAPI backend."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx


DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)


class ApiError(Exception):
    """Safe error carrying only information suitable for display in the UI."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: Any = None,
    ) -> None:
        # Never include tokens, passwords, headers, or raw provider output.
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class AuthenticationError(ApiError):
    """Raised when the backend returns 401 — session should be cleared."""


class ApiClient:
    """Thin HTTP wrapper that enforces the Streamlit → FastAPI boundary."""

    def __init__(
        self,
        base_url: str = DEFAULT_API_BASE_URL,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout or DEFAULT_TIMEOUT

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.status_code == 401:
            raise AuthenticationError(
                "Session expired or invalid — please log in again.",
                status_code=401,
            )
        if response.status_code == 409:
            raise ApiError(
                "An account with this email already exists.",
                status_code=409,
            )
        if response.status_code == 422:
            detail = None
            try:
                body = response.json()
                detail = body.get("detail")
            except Exception:
                pass
            raise ApiError(
                "The request contained invalid data.",
                status_code=422,
                detail=detail,
            )
        if response.status_code == 502:
            raise ApiError(
                "The AI decision service returned an unusable result. Please try again.",
                status_code=502,
            )
        if response.status_code == 503:
            raise ApiError(
                "The AI decision service is currently unavailable. Please try later.",
                status_code=503,
            )
        if response.status_code >= 400:
            message = "An unexpected error occurred."
            try:
                body = response.json()
                if "detail" in body and isinstance(body["detail"], str):
                    message = body["detail"]
            except Exception:
                pass
            raise ApiError(message, status_code=response.status_code)

        try:
            return response.json()
        except Exception:
            raise ApiError("Received a malformed response from the server.")

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method,
                    self._url(path),
                    headers=self._headers(token),
                    json=json_body,
                    params=params,
                )
        except httpx.ConnectError:
            raise ApiError(
                "Cannot connect to the backend. Is the API server running?",
            ) from None
        except httpx.TimeoutException:
            raise ApiError(
                "The request timed out. Please try again.",
            ) from None
        except httpx.HTTPError:
            raise ApiError(
                "A network error occurred. Please check your connection.",
            ) from None
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def register(self, email: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/register",
            json_body={"email": email, "password": password},
        )

    def login(self, email: str, password: str) -> str:
        """Return the bearer token on success."""
        data = self._request(
            "POST",
            "/login",
            json_body={"email": email, "password": password},
        )
        token = data.get("access_token")
        if not token or not isinstance(token, str):
            raise ApiError("Login succeeded but no token was returned.")
        return token

    def get_current_user(self, token: str) -> dict[str, Any]:
        return self._request("GET", "/me", token=token)

    def create_ticket(
        self,
        token: str,
        *,
        message: str,
        order_value_inr: Decimal | float | None = None,
        days_since_delivery: int | None = None,
        days_since_dispatch: int | None = None,
        product_type: str | None = None,
        opened_status: str | None = None,
        order_status: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"message": message}
        # Explicitly include null-valued fields so the backend sees them.
        body["order_value_inr"] = (
            float(order_value_inr) if order_value_inr is not None else None
        )
        body["days_since_delivery"] = days_since_delivery
        body["days_since_dispatch"] = days_since_dispatch
        body["product_type"] = product_type
        body["opened_status"] = opened_status
        body["order_status"] = order_status
        return self._request("POST", "/tickets", token=token, json_body=body)

    def list_tickets(
        self,
        token: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._request(
            "GET",
            "/tickets",
            token=token,
            params={"limit": limit, "offset": offset},
        )

    def get_ticket(self, token: str, ticket_id: int) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/tickets/{ticket_id}",
            token=token,
        )

    def review_ticket(
        self,
        token: str,
        ticket_id: int,
        *,
        action: str | None = None,
        reason: str | None = None,
        accept: bool = False,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"accept": accept}
        if action:
            body["action"] = action
        if reason:
            body["reason"] = reason
        return self._request(
            "POST",
            f"/tickets/{ticket_id}/review",
            token=token,
            json_body=body,
        )
