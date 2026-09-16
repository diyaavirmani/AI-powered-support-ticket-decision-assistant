"""Isolated database and API fixtures."""

import atexit
import os
import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DIRECTORY = Path(tempfile.mkdtemp(prefix="decision-assistant-tests-"))
atexit.register(shutil.rmtree, TEST_DIRECTORY, ignore_errors=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DIRECTORY / 'test.db'}"
os.environ["JWT_SECRET"] = "test-only-secret-that-is-longer-than-thirty-two-characters"
os.environ["JWT_ALGORITHM"] = "HS256"

from src.api import app  # noqa: E402
from src.database import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    with SessionLocal() as session:
        yield session
