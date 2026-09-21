"""`python -m app.cli check` — the database and the disk agree (S11, TECH_PLAN §7)."""
import uuid

from app import cli, storage, thumbs
from tests.test_files import upload
from tests.test_thumbs import png, thumb_of


def orphan(settings, data=b"left behind"):
    """Bytes in data/files that no row points at — what a crash mid-delete leaves."""
    file_id = uuid.uuid4().hex
    path = storage.path_for(settings.files_dir, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return file_id


def test_clean_vault(auth_client, settings, capsys):
    upload(auth_client, "a.txt")
    assert cli.main(["check"], settings=settings) == 0
    out = capsys.readouterr().out
    assert "1 files in the database, 1 on disk." in out and "Everything matches." in out


def test_orphan_bytes_are_listed_then_removed(auth_client, settings, capsys):
    upload(auth_client, "keep.txt")
    stray = orphan(settings, b"x" * 2048)
    assert cli.main(["check"], settings=settings) == 0
    out = capsys.readouterr().out
    assert f"orphan: {stray} is on disk with no row (2.0 KB)" in out
    assert "--fix" in out and "free 2.0 KB" in out
    assert storage.path_for(settings.files_dir, stray).exists()  # listing changes nothing

    assert cli.main(["check", "--fix"], settings=settings) == 0
    assert "Removed 1 orphan files" in capsys.readouterr().out
    assert not storage.path_for(settings.files_dir, stray).exists()
    assert len(list(settings.files_dir.rglob("*.*"))) == 0
    assert auth_client.get("/api/files").json()["files"][0]["name"] == "keep.txt"


def test_missing_bytes_are_reported_but_never_deleted(auth_client, settings, capsys):
    file = upload(auth_client, "gone.pdf")
    storage.path_for(settings.files_dir, file["id"]).unlink()
    assert cli.main(["check", "--fix"], settings=settings) == 1
    captured = capsys.readouterr()
    assert f"MISSING: {file['id']} has a row but no bytes" in captured.out
    assert "Restore them from a backup" in captured.err
    assert auth_client.get("/api/files").json()["files"][0]["name"] == "gone.pdf"  # the row stays


def test_wrong_size_on_disk_is_reported(auth_client, settings, capsys):
    file = upload(auth_client, "short.txt", b"12345")
    storage.path_for(settings.files_dir, file["id"]).write_bytes(b"1")
    assert cli.main(["check"], settings=settings) == 1
    assert f"MISSING: {file['id']} is on disk at the wrong size" in capsys.readouterr().out


def test_stray_thumbnails_are_cleaned(auth_client, settings, capsys):
    file = upload(auth_client, "photo.png", png())
    thumb_of(auth_client, file)
    thumb = thumbs.path_for(settings.thumbs_dir, file["id"])
    assert thumb.is_file()
    (settings.thumbs_dir / f"{uuid.uuid4().hex}.webp").write_bytes(b"old thumb")
    (settings.thumbs_dir / f"{uuid.uuid4().hex}.none").write_bytes(b"")
    assert cli.main(["check", "--fix"], settings=settings) == 0
    out = capsys.readouterr().out
    assert "2 thumbnails belong to files that are gone" in out
    assert thumb.is_file()  # the real one stays
    assert len(list(settings.thumbs_dir.iterdir())) == 1


def test_no_database(settings, capsys):
    assert cli.main(["check"], settings=settings) == 1
    assert "No database at" in capsys.readouterr().err
