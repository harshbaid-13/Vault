import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import EXAMPLE_SECRET, ConfigError, Settings

GOOD = "g" * 48
ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("secret", ["", "short-secret", EXAMPLE_SECRET])
def test_bad_session_secret_is_refused_without_echoing_it(secret):
    with pytest.raises(ConfigError) as err:
        Settings.from_env({"SESSION_SECRET": secret})
    assert "SESSION_SECRET" in str(err.value)
    assert "secrets.token_urlsafe" in str(err.value)
    if secret:
        assert secret not in str(err.value)


def test_defaults():
    s = Settings.from_env({"SESSION_SECRET": GOOD})
    assert s.data_dir == Path("/data")
    assert s.db_path == Path("/data/vault.db")
    assert (s.max_upload_size_mb, s.session_days, s.backup_keep) == (2048, 30, 30)
    assert s.cookie_secure is False
    assert s.allowed_origins == ()
    assert s.timezone == "Asia/Kolkata"


def test_every_setting_is_read():
    s = Settings.from_env({
        "SESSION_SECRET": GOOD,
        "VAULT_DATA_DIR": "/tmp/vault-data",
        "VAULT_BACKUP_DIR": "/tmp/vault-backups",
        "MAX_UPLOAD_SIZE_MB": "500",
        "VAULT_COOKIE_SECURE": "true",
        "VAULT_ALLOWED_ORIGINS": "https://office-vault.tail1234.ts.net/, http://localhost:8000",
        "SESSION_DAYS": "7",
        "BACKUP_KEEP": "10",
        "VAULT_TIMEZONE": "UTC",
    })
    assert s.data_dir == Path("/tmp/vault-data")
    assert s.backup_dir == Path("/tmp/vault-backups")
    assert (s.max_upload_size_mb, s.session_days, s.backup_keep) == (500, 7, 10)
    assert s.cookie_secure is True
    assert s.allowed_origins == ("https://office-vault.tail1234.ts.net", "http://localhost:8000")
    assert s.timezone == "UTC"


@pytest.mark.parametrize("name, value", [
    ("MAX_UPLOAD_SIZE_MB", "two gigs"),
    ("MAX_UPLOAD_SIZE_MB", "0"),
    ("VAULT_COOKIE_SECURE", "maybe"),
    ("VAULT_ALLOWED_ORIGINS", "office-vault.ts.net"),
    ("VAULT_TIMEZONE", "Mars/Olympus"),
])
def test_bad_values_are_refused_by_name(name, value):
    with pytest.raises(ConfigError) as err:
        Settings.from_env({"SESSION_SECRET": GOOD, name: value})
    assert name in str(err.value)


def test_server_exits_with_a_message_on_bad_config(tmp_path):
    env = {"PATH": os.environ["PATH"], "VAULT_DATA_DIR": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "app"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 1
    assert "Vault cannot start: SESSION_SECRET is not set" in result.stderr
    assert "Traceback" not in result.stderr


def test_unwritable_data_dir_is_a_clear_error(tmp_path):
    from app.main import create_app

    blocker = tmp_path / "not-a-folder"
    blocker.write_text("a file where the data folder should be")
    with pytest.raises(ConfigError, match="cannot write to the data folder"):
        create_app(Settings(session_secret=GOOD, data_dir=blocker))
