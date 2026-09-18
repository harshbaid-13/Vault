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


# ---- Home and Favorites (S9) -------------------------------------------------------------

import re  # noqa: E402

import pytest  # noqa: E402

from tests.test_files import upload  # noqa: E402
from tests.test_security import assert_no_inline  # noqa: E402


def clip(client, title, content, hidden=False, favorite=False):
    item = client.post("/api/clips", json={"title": title, "content": content, "hidden": hidden}).json()
    if favorite:
        client.patch(f"/api/clips/{item['id']}", json={"favorite": True})
    return item


def note(client, title, body, favorite=False):
    item = client.post("/api/notes", json={"title": title, "body": body}).json()
    if favorite:
        client.patch(f"/api/notes/{item['id']}", json={"favorite": True})
    return item


def link(client, url, title="", favorite=False):
    item = client.post("/api/links", json={"url": url, "title": title}).json()
    if favorite:
        client.patch(f"/api/links/{item['id']}", json={"favorite": True})
    return item


def section(html, heading):
    start = html.index(f">{heading}<")
    end = html.find("</section>", start)
    return html[start:end]


def test_home_empty_state(auth_client):
    html = auth_client.get("/").text
    assert "Nothing here yet." in html and "data-upload" in html and 'action="/clipboard/new"' in html
    assert 'id="home-favorites"' not in html and 'id="home-recent"' not in html


def test_home_favorite_clip_copies_and_stays_masked(auth_client):
    clip(auth_client, "Wi-Fi Password", "mango-rain-4471", hidden=True, favorite=True)
    html = auth_client.get("/").text
    favorites = section(html, "Favorites")
    assert "Wi-Fi Password" in favorites and "••••••••" in favorites
    assert '<textarea class="clip__source" hidden readonly>\nmango-rain-4471</textarea>' in favorites
    assert 'class="copy-btn copy-btn--inline" type="button" data-copy aria-label="Copy Wi-Fi Password"' in favorites
    assert "mango-rain-4471</p>" not in html  # never shown as text
    assert_no_inline(html)


def test_home_favorites_six_clips_first_then_see_all(auth_client, settings):
    for n in range(3):
        link(auth_client, f"site{n}.example", favorite=True)
    for n in range(3):
        note(auth_client, f"note {n}", "x", favorite=True)
    clip(auth_client, "IFSC", "HDFC0001234", favorite=True)
    file = upload(auth_client, "passport.pdf", b"%PDF")
    auth_client.patch(f"/api/files/{file['id']}", json={"favorite": True})
    favorites = section(auth_client.get("/").text, "Favorites")
    rows = re.findall(r'<li class="(?:row|clip clip--compact)"', favorites)
    assert len(rows) == 6
    assert favorites.index("IFSC") < favorites.index("passport.pdf")
    assert 'href="/favorites">See all 8</a>' in favorites


def test_home_recent_mixed_newest_first(auth_client, settings):
    file = upload(auth_client, "old.pdf", b"%PDF")
    note(auth_client, "Shopping list", "milk")
    clip(auth_client, "Bank", "HDFC")
    link(auth_client, "irctc.co.in")
    note(auth_client, "", "")  # empty: left out
    with db.connect(settings.db_path) as conn:
        conn.execute("UPDATE files SET created_at = '2020-01-01T00:00:00Z' WHERE id = ?", (file["id"],))
        conn.execute("UPDATE notes SET updated_at = '2026-01-02T00:00:00Z'")
    for n in range(8):
        upload(auth_client, f"new-{n:02}.jpg")
    recent = section(auth_client.get("/").text, "Recent")
    rows = re.findall(r'<li class="(?:row|clip clip--compact)"', recent)
    assert len(rows) == 10
    assert "old.pdf" not in recent and "Shopping list" not in recent  # older than the ten newest
    assert "HDFC" in recent and "irctc" in recent
    assert "src=\"/api/files/" in recent  # image rows carry thumbnails


def test_favorites_page_grouped_and_filtered(auth_client):
    clip(auth_client, "Wi-Fi", "pw", favorite=True)
    note(auth_client, "Plans", "x", favorite=True)
    link(auth_client, "192.168.1.1", "Router admin", favorite=True)
    note(auth_client, "Not starred", "x")
    html = auth_client.get("/favorites").text
    headings = re.findall(r'class="section-head__title" id="group-(\w+)">(\w+)<span class="section-head__count">(\d+)', html)
    assert headings == [("notes", "Notes", "1"), ("clips", "Clips", "1"), ("links", "Links", "1")]
    assert "Not starred" not in html
    assert '<a class="chip" href="/favorites" aria-current="page">All</a>' in html
    only = auth_client.get("/favorites?type=links").text
    assert "Router admin" in only and "Plans" not in only
    assert '<a class="chip" href="/favorites?type=links" aria-current="page">Links</a>' in only
    assert "No files in Favorites yet." in auth_client.get("/favorites?type=files").text
    assert "Router admin" in auth_client.get("/favorites?type=nonsense").text
    partial = auth_client.get("/favorites?partial=1").text
    assert "<html" not in partial and "Plans" in partial
    assert_no_inline(html)


def test_favorites_empty(auth_client):
    html = auth_client.get("/favorites").text
    assert "No favorites yet." in html and 'class="chips"' not in html


def test_unfavorited_leaves_favorites(auth_client):
    item = clip(auth_client, "Wi-Fi", "pw", favorite=True)
    auth_client.patch(f"/api/clips/{item['id']}", json={"favorite": False})
    assert "Wi-Fi" not in auth_client.get("/favorites").text
    assert 'id="home-favorites"' not in auth_client.get("/").text


@pytest.mark.parametrize("path", ["/", "/favorites"])
def test_home_and_favorites_need_login(client, path):
    assert client.get(path, follow_redirects=False).status_code == 302
