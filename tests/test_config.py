"""Configuration safety tests."""

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_jwt_secret_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_short_jwt_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret="too-short")
