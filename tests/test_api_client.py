"""Tests for the HTTP API client used by Streamlit.

Every test uses mocked HTTP transport — no live FastAPI, Gemini, or network.
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.api_client import ApiClient, ApiError, AuthenticationError


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _mock_response(
    status_code: int = 200,
    json_body: dict | list | None = None,
    text: str = "",
) -> httpx.Response:
    if json_body is not None:
        content = json.dumps(json_body).encode("utf-8")
        headers = {"content-type": "application/json"}
    else:
        content = text.encode("utf-8")
        headers = {}
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers=headers,
        request=httpx.Request("GET", "http://test"),
    )


def _patched_client(response: httpx.Response) -> tuple[ApiClient, MagicMock]:
    """Return a client with a mocked httpx.Client.request."""
    mock_request = MagicMock(return_value=response)
    client = ApiClient(base_url="http://testapi:8000")
    return client, mock_request


def _apply_mock(mock_request: MagicMock):
    """Context manager patch for httpx.Client."""
    mock_http = MagicMock()
    mock_http.__enter__ = MagicMock(return_value=mock_http)
    mock_http.__exit__ = MagicMock(return_value=False)
    mock_http.request = mock_request
    return patch("src.api_client.httpx.Client", return_value=mock_http)


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

class TestRegister:
    def test_register_sends_correct_json(self):
        resp = _mock_response(201, {"id": 1, "email": "a@b.com", "created_at": "2026-01-01T00:00:00Z"})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            result = client.register("a@b.com", "securepassword")
        call_kwargs = mock_req.call_args
        assert call_kwargs[1]["json"] == {"email": "a@b.com", "password": "securepassword"}
        assert result["email"] == "a@b.com"

    def test_duplicate_registration_raises_409(self):
        resp = _mock_response(409, {"detail": "Email already registered"})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req), pytest.raises(ApiError) as exc_info:
            client.register("dup@b.com", "securepassword")
        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value)


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------

class TestLogin:
    def test_login_returns_token(self):
        resp = _mock_response(200, {"access_token": "jwt123", "token_type": "bearer"})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            token = client.login("a@b.com", "password123!")
        assert token == "jwt123"
        call_kwargs = mock_req.call_args
        assert call_kwargs[1]["json"] == {"email": "a@b.com", "password": "password123!"}

    def test_login_invalid_credentials_raises_401(self):
        resp = _mock_response(401, {"detail": "Invalid email or password"})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req), pytest.raises(AuthenticationError) as exc_info:
            client.login("a@b.com", "wrong")
        assert exc_info.value.status_code == 401


# ------------------------------------------------------------------
# Authenticated calls
# ------------------------------------------------------------------

class TestAuthenticatedCalls:
    def test_bearer_header_sent(self):
        resp = _mock_response(200, {"id": 1, "email": "a@b.com", "created_at": "2026-01-01T00:00:00Z"})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            client.get_current_user("mytoken")
        headers = mock_req.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer mytoken"

    def test_list_tickets_uses_correct_path(self):
        resp = _mock_response(200, json_body=[])
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            client.list_tickets("tok")
        call_args = mock_req.call_args
        assert "/tickets" in call_args[0][1]
        assert call_args[0][0] == "GET"

    def test_get_ticket_uses_correct_path(self):
        resp = _mock_response(200, {"id": 42, "message": "test", "decision": {}})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            client.get_ticket("tok", 42)
        call_args = mock_req.call_args
        assert "/tickets/42" in call_args[0][1]


# ------------------------------------------------------------------
# Ticket creation
# ------------------------------------------------------------------

class TestTicketCreation:
    def test_null_values_preserved(self):
        resp = _mock_response(201, {
            "id": 1, "message": "help", "decision": {"action": "WAIT_AND_TRACK"},
            "order_value_inr": None, "days_since_delivery": None,
            "days_since_dispatch": None, "product_type": None,
            "opened_status": None, "order_status": None,
            "created_at": "2026-01-01T00:00:00Z",
        })
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            client.create_ticket("tok", message="help")
        body = mock_req.call_args[1]["json"]
        assert body["days_since_delivery"] is None
        assert body["days_since_dispatch"] is None
        assert body["order_value_inr"] is None
        assert body["product_type"] is None
        assert body["opened_status"] is None
        assert body["order_status"] is None

    def test_issue_type_not_sent(self):
        resp = _mock_response(201, {
            "id": 1, "message": "help", "decision": {"action": "WAIT_AND_TRACK"},
            "order_value_inr": None, "days_since_delivery": None,
            "days_since_dispatch": None, "product_type": None,
            "opened_status": None, "order_status": None,
            "created_at": "2026-01-01T00:00:00Z",
        })
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            client.create_ticket("tok", message="damaged item")
        body = mock_req.call_args[1]["json"]
        assert "issue_type" not in body

    def test_values_sent_correctly(self):
        resp = _mock_response(201, {
            "id": 1, "message": "broken", "decision": {},
            "order_value_inr": 3500.0, "days_since_delivery": 2,
            "days_since_dispatch": None, "product_type": "non_food",
            "opened_status": "opened", "order_status": "delivered",
            "created_at": "2026-01-01T00:00:00Z",
        })
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            client.create_ticket(
                "tok",
                message="broken",
                order_value_inr=3500,
                days_since_delivery=2,
                product_type="non_food",
                opened_status="opened",
                order_status="delivered",
            )
        body = mock_req.call_args[1]["json"]
        assert body["order_value_inr"] == 3500.0
        assert body["days_since_delivery"] == 2
        assert body["product_type"] == "non_food"


# ------------------------------------------------------------------
# Error mapping
# ------------------------------------------------------------------

class TestErrorMapping:
    def test_timeout_raises_safe_error(self):
        client = ApiClient(base_url="http://testapi:8000")
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.request.side_effect = httpx.ReadTimeout("timeout")
        with patch("src.api_client.httpx.Client", return_value=mock_http):
            with pytest.raises(ApiError, match="timed out"):
                client.login("a@b.com", "pw")

    def test_connection_failure_raises_safe_error(self):
        client = ApiClient(base_url="http://testapi:8000")
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.request.side_effect = httpx.ConnectError("refused")
        with patch("src.api_client.httpx.Client", return_value=mock_http):
            with pytest.raises(ApiError, match="Cannot connect"):
                client.register("a@b.com", "pw")

    def test_422_mapped(self):
        resp = _mock_response(422, {"detail": [{"msg": "bad"}]})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req), pytest.raises(ApiError) as exc_info:
            client.create_ticket("tok", message="x")
        assert exc_info.value.status_code == 422

    def test_502_mapped(self):
        resp = _mock_response(502, {"detail": "bad gateway"})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req), pytest.raises(ApiError) as exc_info:
            client.create_ticket("tok", message="x")
        assert exc_info.value.status_code == 502
        assert "unusable" in str(exc_info.value)

    def test_503_mapped(self):
        resp = _mock_response(503, {"detail": "unavailable"})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req), pytest.raises(ApiError) as exc_info:
            client.create_ticket("tok", message="x")
        assert exc_info.value.status_code == 503
        assert "unavailable" in str(exc_info.value)


# ------------------------------------------------------------------
# Security: tokens and passwords do not leak
# ------------------------------------------------------------------

class TestSecurityLeaks:
    def test_token_not_in_auth_error(self):
        resp = _mock_response(401, {"detail": "Invalid"})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            try:
                client.get_current_user("secret-jwt-token-value")
            except AuthenticationError as exc:
                assert "secret-jwt-token-value" not in str(exc)
                assert "secret-jwt-token-value" not in repr(exc)

    def test_password_not_in_registration_error(self):
        resp = _mock_response(422, {"detail": [{"msg": "too short"}]})
        client, mock_req = _patched_client(resp)
        with _apply_mock(mock_req):
            try:
                client.register("a@b.com", "my-super-secret-pw")
            except ApiError as exc:
                assert "my-super-secret-pw" not in str(exc)
                assert "my-super-secret-pw" not in repr(exc)

    def test_token_not_in_timeout_error(self):
        client = ApiClient(base_url="http://testapi:8000")
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.request.side_effect = httpx.ReadTimeout("timeout")
        with patch("src.api_client.httpx.Client", return_value=mock_http):
            try:
                client.get_current_user("secret-token")
            except ApiError as exc:
                assert "secret-token" not in str(exc)


# ------------------------------------------------------------------
# Streamlit app import smoke test
# ------------------------------------------------------------------

class TestStreamlitImport:
    def test_app_module_imports_without_database_or_gemini(self):
        """Verify the Streamlit app can be imported without touching the DB or Gemini."""
        # streamlit_app imports src.api_client which uses httpx — no DB/Gemini.
        import importlib
        mod = importlib.import_module("src.api_client")
        assert hasattr(mod, "ApiClient")
        assert hasattr(mod, "ApiError")
        assert hasattr(mod, "AuthenticationError")

        app_mod = importlib.import_module("streamlit_app")
        assert hasattr(app_mod, "main")
        assert hasattr(app_mod, "render_auth")
        assert hasattr(app_mod, "render_new_decision")
        assert hasattr(app_mod, "render_history")
        assert hasattr(app_mod, "format_action_label")
        assert hasattr(app_mod, "format_issue_type")
        assert hasattr(app_mod, "get_action_style")

    def test_presentation_helpers(self):
        from streamlit_app import format_action_label, format_issue_type, get_action_style

        # format_action_label
        assert format_action_label("REPLACE_CORRECT_ITEM") == "Replace Correct Item"
        assert format_action_label("APPROVE_RETURN") == "Approve Return"
        assert format_action_label("") == "—"
        assert format_action_label(None) == "—"

        # format_issue_type
        assert format_issue_type("damaged") == "Damaged Goods"
        assert format_issue_type("shipping_delay") == "Shipping Delay"
        assert format_issue_type("wrong_item") == "Wrong Item Received"
        assert format_issue_type("cancellation") == "Order Cancellation"
        assert format_issue_type("unknown") == "Unspecified Issue"
        assert format_issue_type(None) == "Unspecified Issue"

        # get_action_style
        approved = get_action_style("APPROVE_RETURN")
        assert approved["category"] == "Approved"
        assert approved["icon"] == ""
        assert "#" in approved["bg"]

        info = get_action_style("REQUEST_PHOTOS")
        assert info["category"] == "Needs Information"
        assert info["icon"] == ""

        action_req = get_action_style("REPLACE_CORRECT_ITEM")
        assert action_req["category"] == "Action Required"

        ineligible = get_action_style("CANNOT_CANCEL_AFTER_DISPATCH")
        assert ineligible["category"] == "Ineligible"
        assert ineligible["icon"] == ""

        fallback = get_action_style("NONEXISTENT_ACTION")
        assert fallback["category"] == "Decision"

    def test_review_ticket_request(self):
        resp = _mock_response(200, {"id": 1, "decision": {"action": "APPROVE_RETURN"}})
        client, mock_req = _patched_client(resp)
        with patch("src.api_client.httpx.Client") as mock_cls:
            _apply_mock(mock_req)
            mock_cls.return_value.__enter__.return_value.request = mock_req
            client.review_ticket("tok", 42, action="APPROVE_RETURN", reason="VIP override", accept=False)

        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "http://testapi:8000/tickets/42/review"
        assert call_args[1]["json"] == {
            "accept": False,
            "action": "APPROVE_RETURN",
            "reason": "VIP override",
        }

    def test_reset_password_request(self):
        resp = _mock_response(200, {"message": "Password reset successfully"})
        client, mock_req = _patched_client(resp)
        with patch("src.api_client.httpx.Client") as mock_cls:
            _apply_mock(mock_req)
            mock_cls.return_value.__enter__.return_value.request = mock_req
            res = client.reset_password("agent@company.com", "NewPassword123!")

        assert res["message"] == "Password reset successfully"
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "http://testapi:8000/reset-password"
        assert call_args[1]["json"] == {
            "email": "agent@company.com",
            "new_password": "NewPassword123!",
        }
