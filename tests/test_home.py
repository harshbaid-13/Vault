import os

from app import VERSION, db
from app.web import size


def test_size_format():
    assert [size(n) for n in (0, 999, 1536, 15 * 1024**2, int(4.2 * 1024**3), 3 * 1024**4)] == [
        "0 B", "999 B", "1.5 KB", "15 MB", "4.2 GB", "3.0 TB",
    ]


def test_settings_needs_login(client):
    assert client.get("/settings", follow_redirects=False).status_code == 302


def test_settings_shows_counts_storage_and_version(auth_client, settings):
    now = db.now()
    with db.connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO files (id, name, size, sha256, mime, kind, created_at, updated_at)"
            " VALUES (?, 'a.pdf', 1536, ?, 'application/pdf', 'pdf', ?, ?)", ("a" * 32, "0" * 64, now, now))
        conn.executemany("INSERT INTO notes (title, created_at, updated_at) VALUES ('n', ?, ?)", [(now, now)] * 2)
        conn.execute("INSERT INTO clips (title, created_at, updated_at) VALUES ('c', ?, ?)", (now, now))
    html = auth_client.get("/settings").text
    assert "1.5 KB used ·" in html and " free</dd>" in html
    assert '<dt class="kv__key">Files</dt><dd class="kv__value">1</dd>' in html
    assert '<dt class="kv__key">Notes</dt><dd class="kv__value">2</dd>' in html
    assert '<dt class="kv__key">Clips</dt><dd class="kv__value">1</dd>' in html
    assert '<dt class="kv__key">Links</dt><dd class="kv__value">0</dd>' in html
    assert f'<dd class="kv__value">{VERSION}</dd>' in html
    assert 'data-check="https"' in html and 'data-check="clipboard"' in html
    assert 'data-modal-open="modal-password"' in html
    assert 'action="/logout" method="post"' in html


def test_last_backup(auth_client, settings):
    assert '<dt class="kv__key">Last backup</dt><dd class="kv__value">Never</dd>' in auth_client.get("/settings").text
    snapshot = settings.backup_dir / "db" / "vault-2026-09-11_0200.db"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(b"")
    os.utime(snapshot, (1789092000, 1789092000))  # 2026-09-11 02:00 UTC
    assert '<dd class="kv__value">Sep 11, 07:30</dd>' in auth_client.get("/settings").text  # Asia/Kolkata
