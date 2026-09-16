"""Authentication endpoint integration tests."""

from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth import create_access_token, verify_password
from src.config import get_settings
from src.models import User


REGISTER_PAYLOAD = {
    "email": "  Alice.Example@Example.COM ",
    "password": "correct horse battery staple",
}


def register_user(client: TestClient) -> dict:
    response = client.post("/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    return response.json()


def login_user(client: TestClient) -> str:
    response = client.post(
        "/login",
        json={"email": "alice.example@example.com", "password": REGISTER_PAYLOAD["password"]},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_registration_normalizes_email_and_returns_safe_user(client: TestClient) -> None:
    response = client.post("/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice.example@example.com"
    assert set(body) == {"id", "email", "created_at"}
    assert "password" not in response.text


def test_stored_password_is_argon2_hash(
    client: TestClient, db_session: Session
) -> None:
    register_user(client)

    user = db_session.scalar(select(User))
    assert user is not None
    assert user.password_hash != REGISTER_PAYLOAD["password"]
    assert user.password_hash.startswith("$argon2")
    assert verify_password(REGISTER_PAYLOAD["password"], user.password_hash)


def test_duplicate_normalized_email_is_rejected(client: TestClient) -> None:
    register_user(client)

    response = client.post(
        "/register",
        json={"email": "ALICE.EXAMPLE@example.com", "password": "another valid password"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}


def test_invalid_registration_inputs_do_not_echo_password(client: TestClient) -> None:
    plaintext = "too-short"
    response = client.post(
        "/register", json={"email": "not-an-email", "password": plaintext}
    )

    assert response.status_code == 422
    assert plaintext not in response.text
    assert {tuple(error["loc"]) for error in response.json()["detail"]} == {
        ("body", "email"),
        ("body", "password"),
    }


def test_login_succeeds_and_issues_required_claims(client: TestClient) -> None:
    user = register_user(client)

    response = client.post(
        "/login",
        json={"email": " ALICE.EXAMPLE@EXAMPLE.COM ", "password": REGISTER_PAYLOAD["password"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type"}
    assert body["token_type"] == "bearer"
    settings = get_settings()
    claims = jwt.decode(
        body["access_token"],
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
    )
    assert claims["sub"] == str(user["id"])
    assert {"sub", "iat", "exp"}.issubset(claims)


def test_wrong_password_and_unknown_email_have_identical_failures(
    client: TestClient,
) -> None:
    register_user(client)
    wrong_password = client.post(
        "/login",
        json={"email": "alice.example@example.com", "password": "this is the wrong password"},
    )
    unknown_email = client.post(
        "/login",
        json={"email": "nobody@example.com", "password": "this is the wrong password"},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {
        "detail": "Invalid email or password"
    }
    assert wrong_password.headers["www-authenticate"] == "Bearer"
    assert unknown_email.headers["www-authenticate"] == "Bearer"


def test_me_returns_safe_user_for_valid_token(client: TestClient) -> None:
    registered = register_user(client)
    token = login_user(client)

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == registered
    assert "password_hash" not in response.text


def test_me_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "authorization",
    ["Bearer not-a-jwt", "Basic dXNlcjpwYXNz", "Bearer"],
)
def test_me_rejects_malformed_or_invalid_tokens(
    client: TestClient, authorization: str
) -> None:
    response = client.get("/me", headers={"Authorization": authorization})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


def test_me_rejects_token_with_invalid_signature(client: TestClient) -> None:
    token = jwt.encode(
        {"sub": "1", "iat": 1, "exp": 4_000_000_000},
        "a-different-secret-that-is-long-enough-for-this-test",
        algorithm="HS256",
    )

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_me_rejects_expired_token(client: TestClient) -> None:
    user = register_user(client)
    token = create_access_token(user["id"], expires_delta=timedelta(seconds=-1))

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_me_rejects_token_for_missing_user(client: TestClient) -> None:
    token = create_access_token(999_999)

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_invalid_request_body_is_rejected(client: TestClient) -> None:
    response = client.post("/login", content="not-json", headers={"Content-Type": "application/json"})

    assert response.status_code == 422
