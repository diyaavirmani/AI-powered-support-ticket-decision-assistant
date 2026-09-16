"""FastAPI application and authentication endpoints."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from src.database import get_db, init_db
from src.dependencies import get_current_user
from src.models import User
from src.schemas import LoginRequest, RegistrationRequest, TokenResponse, UserResponse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Support Decision Assistant", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for error in exc.errors():
        sanitized = {key: value for key, value in error.items() if key != "input"}
        errors.append(sanitized)
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": errors}))


@app.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegistrationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    existing_user = db.scalar(select(User).where(User.email == str(request.email)))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=str(request.email),
        password_hash=hash_password(request.password.get_secret_value()),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None
    db.refresh(user)
    return user


@app.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(request.email)))
    encoded_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_matches = verify_password(
        request.password.get_secret_value(), encoded_hash
    )
    if user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(user.id))


@app.get("/me", response_model=UserResponse)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
