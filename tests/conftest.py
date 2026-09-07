import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("OPERATOR_PASSWORD", "stage-one-test-password")
os.environ.setdefault("SESSION_SECRET", "stage-one-test-secret-with-more-than-32-characters")
os.environ.setdefault("COOKIE_SECURE", "false")

from app.config import Settings  # noqa: E402
from app.database import Base  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def app(tmp_path: Path):
    database_path = tmp_path / "takaven-test.db"
    settings = Settings(
        database_url=f"sqlite:///{database_path.as_posix()}",
        operator_password="stage-one-test-password",
        session_secret="stage-one-test-secret-with-more-than-32-characters",
        cookie_secure=False,
        log_level="WARNING",
    )
    application = create_app(settings)
    Base.metadata.create_all(application.state.engine)
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def authenticated_client(client: TestClient):
    response = client.post(
        "/login", data={"password": "stage-one-test-password"}, follow_redirects=False
    )
    assert response.status_code == 303
    return client
