"""Password hashing and JWT creation/validation."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from pwdlib import PasswordHash

from src.config import Settings, get_settings


password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-account-password")


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def create_access_token(
    user_id: int,
    *,
    expires_delta: Optional[timedelta] = None,
    settings: Optional[Settings] = None,
) -> str:
    active_settings = settings or get_settings()
    now = datetime.now(timezone.utc)
    expires = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=active_settings.access_token_expire_minutes)
    )
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": expires},
        active_settings.jwt_secret.get_secret_value(),
        algorithm=active_settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Optional[Settings] = None) -> int:
    active_settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            active_settings.jwt_secret.get_secret_value(),
            algorithms=[active_settings.jwt_algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
        user_id = int(payload["sub"])
        if user_id <= 0:
            raise ValueError("nonpositive subject")
        return user_id
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError from exc
