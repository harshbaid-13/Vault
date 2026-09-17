import sqlite3

import pytest

from app import db
from app.main import create_app


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_startup_creates_folders_and_empties_tmp(settings):
    (settings.data_dir / "tmp" / "half-upload").mkdir(parents=True)
    (settings.data_dir / "tmp" / "abc.part").write_bytes(b"partial")
    create_app(settings)
    for name in ("files", "thumbs", "tmp"):
        assert (settings.data_dir / name).is_dir()
    assert list((settings.data_dir / "tmp").iterdir()) == []


def test_migrations_are_safe_to_run_again(settings):
    create_app(settings)
    create_app(settings)
    with sqlite3.connect(settings.db_path) as conn:
        assert conn.execute("SELECT version FROM schema_version").fetchall() == [(1,)]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert {"settings", "folders", "files", "notes", "clips", "links"} <= tables


def test_failed_migration_rolls_back(tmp_path):
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_ok.sql").write_text("CREATE TABLE one (x INTEGER);")
    (migrations / "002_broken.sql").write_text("CREATE TABLE two (x INTEGER);\nTHIS IS NOT SQL;")
    path = tmp_path / "vault.db"
    with pytest.raises(sqlite3.Error):
        db.migrate(path, migrations)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 1
        assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'two'").fetchone() is None


def test_folder_names_unique_per_parent_including_root(app, settings):
    with db.connect(settings.db_path) as conn:
        conn.execute("INSERT INTO folders (name, created_at, updated_at) VALUES ('Bills', ?, ?)", (db.now(), db.now()))
    with pytest.raises(sqlite3.IntegrityError), db.connect(settings.db_path) as conn:
        conn.execute("INSERT INTO folders (name, created_at, updated_at) VALUES ('bills', ?, ?)", (db.now(), db.now()))


def test_foreign_keys_are_enforced(app, settings):
    with pytest.raises(sqlite3.IntegrityError), db.connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO folders (parent_id, name, created_at, updated_at) VALUES (999, 'x', ?, ?)",
            (db.now(), db.now()),
        )


def test_timestamps_are_fixed_width_utc():
    stamp = db.now()
    assert len(stamp) == 20 and stamp.endswith("Z") and stamp[10] == "T"
