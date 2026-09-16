"""Reusable FastAPI authentication dependencies."""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.auth import InvalidTokenError, decode_access_token
from src.database import get_db
from src.models import User


bearer_scheme = HTTPBearer(auto_error=False)


def authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)
    ],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_error()

    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise authentication_error() from None

    user = db.get(User, user_id)
    if user is None:
        raise authentication_error()
    return user
