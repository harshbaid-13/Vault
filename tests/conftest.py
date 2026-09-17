import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

TEST_SECRET = "test-session-secret-" + "x" * 40


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


@pytest.fixture
def client(app):
    # Same-origin Origin by default, so S2's Origin check passes for normal requests.
    with TestClient(app, base_url="http://testserver", headers={"Origin": "http://testserver"}) as c:
        yield c
