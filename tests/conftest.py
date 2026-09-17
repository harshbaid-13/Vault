import pytest
from fastapi.testclient import TestClient

from app import auth
from app.config import Settings
from app.main import create_app

TEST_SECRET = "test-session-secret-" + "x" * 40
PASSWORD = "correct horse battery"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        session_secret=TEST_SECRET,
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        max_upload_size_mb=2,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


def make_client(app):
    # Same-origin Origin by default, so the Origin check passes for normal requests.
    return TestClient(app, base_url="http://testserver", headers={"Origin": "http://testserver"})


@pytest.fixture
def client(app):
    """Logged out."""
    with make_client(app) as c:
        yield c


def log_in(client, password=PASSWORD):
    r = client.post("/login", data={"password": password}, follow_redirects=False)
    assert r.status_code == 303, r.status_code
    return client


@pytest.fixture
def auth_client(app, settings, client):
    """Password set, logged in."""
    auth.set_password(settings.db_path, PASSWORD)
    return log_in(client)
