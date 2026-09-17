import logging
import re

import pytest

from app import db
from tests.test_security import assert_no_inline


def create(client, **fields):
    r = client.post("/api/notes", json=fields)
    assert r.status_code == 201, r.text
    return r.json()


def set_updated_at(settings, note_id, stamp):
    with db.connect(settings.db_path) as conn:
        conn.execute("UPDATE notes SET updated_at = ? WHERE id = ?", (stamp, note_id))


# ---- API ------------------------------------------------------------------------------

def test_create_and_list(auth_client, settings):
    note = create(auth_client, title="Shopping list", body="milk\nbread")
    assert set(note) == {"id", "title", "body", "favorite", "created_at", "updated_at"}
    assert note["favorite"] is False
    assert create(auth_client, body="only a body")["title"] == ""
    old = create(auth_client, title="old")
    set_updated_at(settings, old["id"], "2025-01-01T00:00:00Z")
    auth_client.patch(f"/api/notes/{old['id']}", json={"favorite": True})
    titles = [n["title"] for n in auth_client.get("/api/notes").json()["notes"]]
    assert titles == ["old", "", "Shopping list"]  # favorite first even when older; ties newest id first


def test_autosave_patch_updates_updated_at(auth_client, settings):
    note = create(auth_client, title="t", body="first")
    set_updated_at(settings, note["id"], "2026-01-01T00:00:00Z")
    r = auth_client.patch(f"/api/notes/{note['id']}", json={"title": "t", "body": "first words"})
    assert r.status_code == 200
    assert r.json()["body"] == "first words"
    assert r.json()["updated_at"] > "2026-01-01T00:00:00Z"
    set_updated_at(settings, note["id"], "2026-01-01T00:00:00Z")
    assert auth_client.patch(f"/api/notes/{note['id']}", json={"favorite": True}).json()["updated_at"] == "2026-01-01T00:00:00Z"


def test_last_save_wins(auth_client):
    note = create(auth_client, body="start")
    auth_client.patch(f"/api/notes/{note['id']}", json={"body": "from the phone"})
    auth_client.patch(f"/api/notes/{note['id']}", json={"body": "from the laptop"})
    assert auth_client.get("/api/notes").json()["notes"][0]["body"] == "from the laptop"


def test_search(auth_client):
    create(auth_client, title="Car service", body="Booked for Saturday")
    create(auth_client, title="Books", body="Piranesi 50% read")
    def search(q):
        return [n["title"] for n in auth_client.get("/api/notes", params={"q": q}).json()["notes"]]
    assert search("saturday") == ["Car service"]
    assert search("book") == ["Books", "Car service"]
    assert search("50%") == ["Books"]
    assert search("_") == []


def test_delete(auth_client):
    note = create(auth_client, title="gone")
    assert auth_client.delete(f"/api/notes/{note['id']}").status_code == 204
    assert auth_client.get("/api/notes").json()["notes"] == []
    r = auth_client.delete(f"/api/notes/{note['id']}")
    assert r.status_code == 404 and r.json() == {"error": "That note no longer exists."}


@pytest.mark.parametrize("body, message", [
    ({"title": "x" * 201}, "The title is too long (max 200 characters)."),
    ({"body": "x" * 1_000_001}, "The note is too long (max 1,000,000 characters)."),
    ({"body": 5}, "That request wasn't understood."),
    ({"content": "x"}, "That request wasn't understood."),
])
def test_validation(auth_client, body, message):
    r = auth_client.post("/api/notes", json=body)
    assert r.status_code == 422 and r.json() == {"error": message}
    note = create(auth_client, title="t")
    assert auth_client.patch(f"/api/notes/{note['id']}", json=body).status_code == 422
    assert auth_client.patch(f"/api/notes/{note['id']}", json={"favorite": 1}).status_code == 422


@pytest.mark.parametrize("method, path", [
    ("GET", "/api/notes"), ("POST", "/api/notes"), ("PATCH", "/api/notes/1"), ("DELETE", "/api/notes/1"),
])
def test_logged_out_api_is_401(client, method, path):
    assert client.request(method, path, json={} if method in ("POST", "PATCH") else None).status_code == 401


def test_logged_out_pages_go_to_login(client):
    for method, path in [("GET", "/notes"), ("POST", "/notes/new"), ("GET", "/notes/1")]:
        r = client.request(method, path, follow_redirects=False)
        assert r.status_code in (302, 303) and r.headers["location"].startswith("/login")


def test_logs_hold_no_note_text(auth_client, caplog):
    with caplog.at_level(logging.DEBUG):
        note = create(auth_client, title="Diary title", body="private words")
        auth_client.patch(f"/api/notes/{note['id']}", json={"body": "more private words"})
        auth_client.delete(f"/api/notes/{note['id']}")
    assert "private" not in caplog.text and "Diary" not in caplog.text
    assert f"Note {note['id']} deleted" in caplog.text


# ---- Pages ----------------------------------------------------------------------------

def rows(html):
    return re.findall(r'<li class="row">.*?</li>', html, re.S)


def test_empty_list(auth_client):
    html = auth_client.get("/notes").text
    assert "No notes yet." in html and 'action="/notes/new" method="post"' in html


def test_new_opens_the_editor_with_the_cursor_in_the_body(auth_client, settings):
    r = auth_client.post("/notes/new", follow_redirects=False)
    assert r.status_code == 303
    html = auth_client.get(r.headers["location"]).text
    assert 'data-focus="#editor-body"' in html
    assert 'name="body"' in html and 'placeholder="Start writing…"' in html
    assert "data-editor-hidden" not in html
    assert '<button class="btn btn--primary" type="button" data-editor-save>Save</button>' in html
    assert 'data-copy-from="#editor-body"' in html and 'data-action="delete"' in html
    assert "interactive-widget=resizes-content" in html
    assert_no_inline(html)
    # Empty notes aren't listed; the editor deletes them on leaving.
    assert "No notes yet." in auth_client.get("/notes").text
    with db.connect(settings.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 1


def test_rows(auth_client, settings):
    titled = create(auth_client, title="Shopping list", body="\nmilk, bread\ncoffee")
    untitled = create(auth_client, body="Car service\nBooked for Sat")
    set_updated_at(settings, titled["id"], "2020-05-04T10:00:00Z")
    auth_client.patch(f"/api/notes/{titled['id']}", json={"favorite": True})
    first, second = rows(auth_client.get("/notes").text)
    assert f'href="/notes/{titled["id"]}">Shopping list</a>' in first
    assert "May 4, 2020 · milk, bread</span>" in first
    assert 'class="pin-mark"' in first and "data-favorite" in first
    assert f'href="/notes/{untitled["id"]}">Car service</a>' in second
    assert "Just now · Booked for Sat</span>" in second
    assert f'data-item="/api/notes/{untitled["id"]}"' in second
    assert_no_inline(auth_client.get("/notes").text)


def test_note_is_escaped(auth_client):
    note = create(auth_client, title="<b>x</b>", body="</textarea><script>alert(1)</script>")
    for path in ("/notes", f"/notes/{note['id']}"):
        html = auth_client.get(path).text
        assert "<b>x</b>" not in html and "<script>alert" not in html


def test_editor_404(auth_client):
    assert auth_client.get("/notes/999").status_code == 404


def test_partial(auth_client):
    create(auth_client, title="t")
    html = auth_client.get("/notes?partial=1").text
    assert '<li class="row">' in html and "<html" not in html and 'id="sheet-note"' not in html
