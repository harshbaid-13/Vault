import dataclasses
import logging
import sqlite3

import pytest

from app import backup, db, restore, storage
from tests.test_files import upload
from tests.test_home import note


@pytest.fixture
def vault(auth_client, settings):
    """A vault with two files (one in a folder) and a note."""
    folder = auth_client.post("/api/folders", json={"name": "Bills", "parent_id": None}).json()
    a = upload(auth_client, "passport.pdf", b"%PDF passport bytes")
    b = auth_client.post(f"/api/files?folder_id={folder['id']}", content=b"photo bytes" * 1000,
                         headers={"Content-Type": "application/octet-stream", "X-File-Name": "photo.jpg"}).json()
    note(auth_client, "Test note", "remember me")
    return {"client": auth_client, "files": [a, b]}


def run(module, settings, *args):
    return module.main(list(args), settings=settings)


def notes_in(path):
    conn = sqlite3.connect(path)
    try:
        return [row[0] for row in conn.execute("SELECT title FROM notes ORDER BY id")]
    finally:
        conn.close()


def mirror_ids(settings):
    return sorted(p.name for p in backup.mirror_files(settings))


def test_backup_snapshot_and_mirror(vault, settings, capsys):
    assert run(backup, settings) == 0
    [snapshot] = backup.snapshots(settings)
    assert snapshot.name.startswith("vault-") and snapshot.suffix == ".db"
    assert notes_in(snapshot) == ["Test note"]
    assert mirror_ids(settings) == sorted(f["id"] for f in vault["files"])
    for f in vault["files"]:
        assert backup.mirror_path(settings, f["id"]).read_bytes() == storage.path_for(settings.files_dir, f["id"]).read_bytes()
    out = capsys.readouterr().out
    assert "Backup done:" in out and "2 new copied" in out
    assert "passport" not in out and "Test note" not in out  # ids and counts only
    assert not list(settings.backup_dir.rglob("*.part"))
    # One self-contained file per snapshot: no -wal / -shm beside it, even after it's been read.
    backup.check_database(snapshot)
    assert [p.name for p in (settings.backup_dir / "db").iterdir()] == [snapshot.name]


def test_second_backup_copies_only_new_files(vault, settings, capsys):
    run(backup, settings)
    upload(vault["client"], "new.txt", b"new")
    capsys.readouterr()
    assert run(backup, settings) == 0
    assert "1 new copied" in capsys.readouterr().out
    assert len(backup.snapshots(settings)) == 2  # same minute: the second gets a -2 suffix
    assert len(mirror_ids(settings)) == 3


def test_round_trip_restore(vault, settings, capsys):
    """Back up, delete a note and a file, restore: both are back, and the old data is kept aside."""
    client = vault["client"]
    assert run(backup, settings) == 0
    [snapshot] = backup.snapshots(settings)
    note_id = client.get("/api/notes").json()["notes"][0]["id"]
    client.delete(f"/api/notes/{note_id}")
    gone = vault["files"][0]
    client.delete(f"/api/files/{gone['id']}")
    after = upload(client, "after-backup.txt", b"later")
    assert client.get("/api/notes").json()["notes"] == []

    assert run(restore, settings, snapshot.name) == 0
    assert notes_in(settings.db_path) == ["Test note"]
    for f in vault["files"]:
        assert storage.path_for(settings.files_dir, f["id"]).read_bytes() == backup.mirror_path(settings, f["id"]).read_bytes()
    # A file uploaded after the snapshot isn't brought in; it waits in the moved-aside data.
    assert not storage.path_for(settings.files_dir, after["id"]).exists()
    [aside] = [p for p in settings.data_dir.iterdir() if p.name.startswith("before-restore-")]
    assert (aside / "vault.db").is_file() and (aside / "files" / after["id"][:2] / after["id"]).is_file()
    out = capsys.readouterr().out
    assert "docker compose up -d" in out and aside.name in out

    # The app starts on the restored data.
    from app.main import create_app
    from tests.conftest import make_client, log_in
    with make_client(create_app(settings)) as fresh:
        log_in(fresh)
        assert [n["title"] for n in fresh.get("/api/notes").json()["notes"]] == ["Test note"]
        assert fresh.get(f"/api/files/{gone['id']}/download").content == b"%PDF passport bytes"
        assert "Bills" in fresh.get("/files").text


def test_restore_into_an_empty_data_folder(vault, settings, tmp_path):
    """A new computer: only backups/ was copied over."""
    run(backup, settings)
    fresh = dataclasses.replace(settings, data_dir=tmp_path / "new-data")
    [snapshot] = backup.snapshots(settings)
    assert run(restore, fresh, str(snapshot)) == 0
    assert notes_in(fresh.db_path) == ["Test note"]
    assert len(list(fresh.files_dir.rglob("*"))) == 4  # 2 prefix folders + 2 files


def test_old_snapshots_are_pruned(vault, settings, capsys):
    keep3 = dataclasses.replace(settings, backup_keep=3)
    for _ in range(5):
        assert run(backup, keep3) == 0
    names = [p.name for p in backup.snapshots(keep3)]
    assert len(names) == 3 and names[-1].endswith("-5.db")
    assert "Removed 1 old snapshot" in capsys.readouterr().out
    assert len(mirror_ids(settings)) == 2  # files are never pruned by a normal run


def test_missing_source_file_makes_an_incomplete_backup(vault, settings, capsys):
    storage.path_for(settings.files_dir, vault["files"][0]["id"]).unlink()
    assert run(backup, settings) == 1
    [snapshot] = backup.snapshots(settings)
    assert snapshot.name.endswith("-INCOMPLETE.db")
    out = capsys.readouterr().out
    assert "Backup INCOMPLETE: 1 of 2" in out and vault["files"][0]["id"] in out
    # An incomplete snapshot is never offered as "last backup" nor restored.
    assert "Never" in vault["client"].get("/settings").text
    assert run(restore, settings, snapshot.name) == 1


def test_damaged_source_file_is_not_mirrored(vault, settings):
    storage.path_for(settings.files_dir, vault["files"][0]["id"]).write_bytes(b"bit rot")
    assert run(backup, settings) == 1
    assert vault["files"][0]["id"] not in mirror_ids(settings)


def test_restore_refuses_before_touching_anything(vault, settings, capsys):
    run(backup, settings)
    [snapshot] = backup.snapshots(settings)
    backup.mirror_path(settings, vault["files"][1]["id"]).unlink()
    before = sorted(p.name for p in settings.data_dir.iterdir())
    assert run(restore, settings, snapshot.name) == 1
    assert "1 of the 2 files" in capsys.readouterr().err
    assert sorted(p.name for p in settings.data_dir.iterdir()) == before
    assert run(restore, settings, "vault-1999-01-01_0000.db") == 1


def test_restore_rejects_a_damaged_snapshot(vault, settings, capsys):
    run(backup, settings)
    [snapshot] = backup.snapshots(settings)
    snapshot.write_bytes(b"not a database at all" * 100)
    assert run(restore, settings, snapshot.name) == 1
    assert "not a readable vault database" in capsys.readouterr().err


def test_restore_puts_data_back_when_a_mirror_file_is_damaged(vault, settings, capsys):
    run(backup, settings)
    [snapshot] = backup.snapshots(settings)
    mirror = backup.mirror_path(settings, vault["files"][0]["id"])
    mirror.write_bytes(b"x" * mirror.stat().st_size)  # right size, wrong bytes
    before = {p.name for p in settings.data_dir.iterdir()}
    live_notes = notes_in(settings.db_path)
    assert run(restore, settings, snapshot.name) == 1
    assert {p.name for p in settings.data_dir.iterdir()} == before
    assert notes_in(settings.db_path) == live_notes
    assert "put back as it was" in capsys.readouterr().out


def test_verify(vault, settings, capsys):
    run(backup, settings)
    capsys.readouterr()
    assert run(backup, settings, "--verify") == 0
    assert "Verify OK: 2 files" in capsys.readouterr().out
    mirror = backup.mirror_path(settings, vault["files"][1]["id"])
    mirror.write_bytes(b"corrupt")
    assert run(backup, settings, "--verify") == 1
    assert f"file {vault['files'][1]['id']}: damaged" in capsys.readouterr().out


def test_prune_mirror_keeps_what_snapshots_need(vault, settings, capsys):
    keep1 = dataclasses.replace(settings, backup_keep=1)
    run(backup, keep1)
    gone = vault["files"][0]
    vault["client"].delete(f"/api/files/{gone['id']}")
    run(backup, keep1)  # the older snapshot (which named the deleted file) is pruned
    assert gone["id"] in mirror_ids(settings)  # a normal run never deletes from the mirror
    capsys.readouterr()
    assert run(backup, keep1, "--prune-mirror") == 0
    assert mirror_ids(settings) == [vault["files"][1]["id"]]
    assert "Removed 1 files" in capsys.readouterr().out


def test_list_snapshots(vault, settings, capsys):
    assert run(restore, settings) == 1  # none yet
    run(backup, settings)
    capsys.readouterr()
    assert run(restore, settings) == 0
    assert "vault-" in capsys.readouterr().out


def test_backup_is_safe_while_the_app_writes(vault, settings):
    """The online backup API copies a consistent database even with a write open elsewhere."""
    writer = sqlite3.connect(settings.db_path)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("INSERT INTO notes (title, created_at, updated_at) VALUES ('uncommitted', ?, ?)", (db.now(), db.now()))
    try:
        assert run(backup, settings) == 0
    finally:
        writer.rollback()
        writer.close()
    [snapshot] = backup.snapshots(settings)
    assert notes_in(snapshot) == ["Test note"]


def test_no_database(settings, capsys):
    assert run(backup, dataclasses.replace(settings, data_dir=settings.data_dir / "nowhere")) == 1
    assert "there is no database" in capsys.readouterr().err


def test_last_backup_on_settings(vault, settings):
    run(backup, settings)
    assert "Never" not in vault["client"].get("/settings").text
