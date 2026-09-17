import logging
import re
from html import unescape

import pytest

from app import db
from tests.test_security import assert_no_inline


def create(client, **fields):
    r = client.post("/api/clips", json={"title": "", "content": "", **fields})
    assert r.status_code == 201, r.text
    return r.json()


def set_updated_at(settings, clip_id, stamp):
    with db.connect(settings.db_path) as conn:
        conn.execute("UPDATE clips SET updated_at = ? WHERE id = ?", (stamp, clip_id))


# ---- API ------------------------------------------------------------------------------

def test_create_returns_the_whole_clip(auth_client):
    clip = create(auth_client, title="Wi-Fi Password", content="mango-rain-4471", hidden=True)
    assert set(clip) == {"id", "title", "content", "hidden", "favorite", "created_at", "updated_at"}
    assert clip["title"] == "Wi-Fi Password"
    assert clip["content"] == "mango-rain-4471"
    assert clip["hidden"] is True and clip["favorite"] is False
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", clip["created_at"])


def test_list_favorites_first_then_newest_modified(auth_client, settings):
    old = create(auth_client, title="old")
    new = create(auth_client, title="new")
    fav = create(auth_client, title="fav")
    set_updated_at(settings, old["id"], "2026-01-01T00:00:00Z")
    set_updated_at(settings, new["id"], "2026-03-01T00:00:00Z")
    set_updated_at(settings, fav["id"], "2025-01-01T00:00:00Z")
    auth_client.patch(f"/api/clips/{fav['id']}", json={"favorite": True})
    titles = [c["title"] for c in auth_client.get("/api/clips").json()["clips"]]
    assert titles == ["fav", "new", "old"]


def test_search_title_and_content_but_never_hidden_content(auth_client):
    create(auth_client, title="Wi-Fi Password", content="mango-rain")
    create(auth_client, title="Bank IFSC", content="HDFC0001234")
    create(auth_client, title="Locker", content="secret-mango", hidden=True)

    def search(q):
        return sorted(c["title"] for c in auth_client.get("/api/clips", params={"q": q}).json()["clips"])

    assert search("wi-fi") == ["Wi-Fi Password"]
    assert search("hdfc") == ["Bank IFSC"]
    assert search("mango") == ["Wi-Fi Password"]  # the hidden clip's content doesn't match
    assert search("locker") == ["Locker"]  # its title does
    assert search("  ") == search("")
    assert len(search("")) == 3


def test_search_treats_like_wildcards_literally(auth_client):
    create(auth_client, title="100% done", content="a_b")
    create(auth_client, title="plain", content="axb")
    assert [c["title"] for c in auth_client.get("/api/clips?q=%25").json()["clips"]] == ["100% done"]
    assert [c["title"] for c in auth_client.get("/api/clips?q=a_b").json()["clips"]] == ["100% done"]
    assert auth_client.get("/api/clips", params={"q": "\\"}).json()["clips"] == []


def test_update_only_changes_what_is_sent(auth_client, settings):
    clip = create(auth_client, title="t", content="c")
    set_updated_at(settings, clip["id"], "2026-01-01T00:00:00Z")

    r = auth_client.patch(f"/api/clips/{clip['id']}", json={"favorite": True, "hidden": True})
    assert r.status_code == 200
    assert r.json()["favorite"] is True and r.json()["hidden"] is True
    assert r.json()["content"] == "c"
    assert r.json()["updated_at"] == "2026-01-01T00:00:00Z"  # starring or hiding isn't an edit

    r = auth_client.patch(f"/api/clips/{clip['id']}", json={"content": "new text"})
    assert r.json()["content"] == "new text" and r.json()["title"] == "t"
    assert r.json()["updated_at"] > "2026-01-01T00:00:00Z"
    assert r.json()["favorite"] is True

    r = auth_client.patch(f"/api/clips/{clip['id']}", json={"favorite": False})
    assert r.json()["favorite"] is False


def test_delete(auth_client):
    clip = create(auth_client, title="gone")
    assert auth_client.delete(f"/api/clips/{clip['id']}").status_code == 204
    assert auth_client.get("/api/clips").json()["clips"] == []
    r = auth_client.delete(f"/api/clips/{clip['id']}")
    assert r.status_code == 404
    assert r.json() == {"error": "That clip no longer exists."}
    assert auth_client.patch(f"/api/clips/{clip['id']}", json={"title": "x"}).status_code == 404


@pytest.mark.parametrize("body, message", [
    ({"title": "x" * 201}, "The title is too long (max 200 characters)."),
    ({"content": "x" * 100_001}, "The text is too long (max 100,000 characters)."),
    ({"title": 5}, "That request wasn't understood."),
    ({"hidden": "yes"}, "That request wasn't understood."),
    ({"hidden": 1}, "That request wasn't understood."),
    ({"favorite": True}, "That request wasn't understood."),  # not on create
    ({"id": 7}, "That request wasn't understood."),
])
def test_create_validation(auth_client, body, message):
    r = auth_client.post("/api/clips", json=body)
    assert r.status_code == 422
    assert r.json() == {"error": message}
    assert auth_client.get("/api/clips").json()["clips"] == []


def test_update_validation_and_limits(auth_client):
    clip = create(auth_client, title="t")
    url = f"/api/clips/{clip['id']}"
    assert auth_client.patch(url, json={"title": "x" * 201}).status_code == 422
    assert auth_client.patch(url, json={"content": "x" * 100_001}).status_code == 422
    assert auth_client.patch(url, json={"favorite": "true"}).status_code == 422
    assert auth_client.patch(url, json={"created_at": "2020"}).status_code == 422
    assert auth_client.patch(url, json=["title"]).status_code == 422
    assert auth_client.get("/api/clips").json()["clips"][0]["title"] == "t"
    # Exactly at the limits is fine.
    r = auth_client.patch(url, json={"title": "é" * 200, "content": "ü" * 100_000})
    assert r.status_code == 200


def test_writes_need_json(auth_client):
    r = auth_client.post("/api/clips", content="title=x", headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 415


def test_foreign_origin_is_blocked(auth_client):
    clip = create(auth_client, title="t")
    r = auth_client.delete(f"/api/clips/{clip['id']}", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert len(auth_client.get("/api/clips").json()["clips"]) == 1


@pytest.mark.parametrize("method, path", [
    ("GET", "/api/clips"), ("POST", "/api/clips"), ("PATCH", "/api/clips/1"), ("DELETE", "/api/clips/1"),
])
def test_logged_out_api_is_401(client, method, path):
    r = client.request(method, path, json={} if method in ("POST", "PATCH") else None)
    assert r.status_code == 401


@pytest.mark.parametrize("method, path", [("GET", "/clipboard"), ("POST", "/clipboard/new"), ("GET", "/clipboard/1")])
def test_logged_out_pages_go_to_login(client, method, path):
    r = client.request(method, path, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"].startswith("/login")


def test_logs_hold_ids_never_titles_or_content(auth_client, caplog):
    with caplog.at_level(logging.DEBUG):
        clip = create(auth_client, title="Bank PIN title", content="4471-secret")
        auth_client.patch(f"/api/clips/{clip['id']}", json={"content": "9999-secret"})
        auth_client.delete(f"/api/clips/{clip['id']}")
    assert "secret" not in caplog.text and "Bank PIN" not in caplog.text
    assert f"Clip {clip['id']} created" in caplog.text


# ---- Pages ----------------------------------------------------------------------------

def clip_blocks(html):
    return re.findall(r'<li class="clip">.*?</li>', html, re.S)


def test_empty_clipboard(auth_client):
    html = auth_client.get("/clipboard").text
    assert "Nothing saved yet." in html
    assert 'action="/clipboard/new" method="post"' in html


def test_new_creates_an_empty_clip_and_opens_the_editor(auth_client, settings):
    r = auth_client.post("/clipboard/new", follow_redirects=False)
    assert r.status_code == 303
    with db.connect(settings.db_path) as conn:
        clip = dict(conn.execute("SELECT id, title, content FROM clips").fetchone())
    assert r.headers["location"] == f"/clipboard/{clip['id']}"
    assert (clip["title"], clip["content"]) == ("", "")

    html = auth_client.get(r.headers["location"]).text
    assert f'data-editor="/api/clips/{clip["id"]}"' in html
    assert 'id="editor-title"' in html and 'name="content"' in html
    assert 'data-editor-hidden' in html and "checked" not in html
    assert 'class="tabbar"' not in html and "app--no-tabbar" in html
    assert 'href="/clipboard" aria-label="Back to Clipboard"' in html
    assert_no_inline(html)
    # Not listed while empty: the editor discards it on leaving.
    assert auth_client.get("/api/clips").json()["clips"] == []
    assert "Nothing saved yet." in auth_client.get("/clipboard").text


def test_editor_shows_the_clip(auth_client):
    clip = create(auth_client, title="Wi-Fi", content="\nstarts with a newline", hidden=True)
    auth_client.patch(f"/api/clips/{clip['id']}", json={"favorite": True})
    html = auth_client.get(f"/clipboard/{clip['id']}").text
    assert 'value="Wi-Fi"' in html
    # The newline right after <textarea> is eaten by the HTML parser, so the content's own survives.
    assert 'placeholder="Paste or type the text to copy…">\n\nstarts with a newline</textarea>' in html
    assert 'data-editor-hidden checked' in html
    assert 'aria-pressed="true" aria-label="Unfavorite this clip"' in html
    assert "Saved · Today, " in html


def test_editor_for_a_missing_clip_is_404(auth_client):
    assert auth_client.get("/clipboard/999").status_code == 404
    assert auth_client.get("/clipboard/abc").status_code == 404


def test_rows_show_title_preview_copy_and_actions(auth_client):
    clip = create(auth_client, title="Bank IFSC code", content="HDFC0001234")
    [row] = clip_blocks(auth_client.get("/clipboard").text)
    assert f'href="/clipboard/{clip["id"]}">Bank IFSC code</a>' in row
    assert '<pre class="clip__content">HDFC0001234</pre>' in row
    assert f'data-item="/api/clips/{clip["id"]}"' in row
    assert 'data-copy aria-label="Copy Bank IFSC code"' in row
    assert "data-reveal" not in row and "clip__masked" not in row and "data-favorite" not in row


def test_hidden_clip_is_masked_but_still_copyable(auth_client):
    create(auth_client, title="Wi-Fi Password", content="mango-rain-4471", hidden=True)
    [row] = clip_blocks(auth_client.get("/clipboard").text)
    assert "clip__masked" in row and "data-reveal" in row and "data-clip-hidden" in row
    assert re.search(r'<pre class="clip__content"\s+hidden>mango-rain-4471</pre>', row)
    assert '<textarea class="clip__source" hidden readonly>\nmango-rain-4471</textarea>' in row


def test_copy_source_holds_the_entire_long_clip(auth_client):
    """DESIGN §3.9: COPY copies the whole clip, never the clipped preview."""
    content = "".join(f"line {i:05d} of a long clip\n" for i in range(2000))[:50_000]
    assert len(content) == 50_000
    create(auth_client, title="Long", content=content)
    [row] = clip_blocks(auth_client.get("/clipboard").text)
    source = re.search(r'<textarea class="clip__source" hidden readonly>\n(.*?)</textarea>', row, re.S).group(1)
    assert unescape(source) == content
    preview = re.search(r'<pre class="clip__content clip__content--long">(.*?)</pre>', row, re.S).group(1)
    assert len(preview) < 1000


def test_favorite_mark_and_untitled(auth_client):
    clip = create(auth_client, content="no title")
    auth_client.patch(f"/api/clips/{clip['id']}", json={"favorite": True})
    [row] = clip_blocks(auth_client.get("/clipboard").text)
    assert 'class="pin-mark" aria-label="Favorite"' in row and "data-favorite" in row
    assert ">Untitled</a>" in row


def test_content_is_escaped(auth_client):
    create(auth_client, title="<img src=x onerror=alert(1)>", content="</textarea><script>alert(2)</script>")
    html = auth_client.get("/clipboard").text
    assert "<img src=x" not in html and "<script>alert" not in html
    assert "&lt;/textarea&gt;&lt;script&gt;" in html
    assert_no_inline(html)


def test_partial_is_only_the_content(auth_client):
    create(auth_client, title="Wi-Fi", content="x")
    html = auth_client.get("/clipboard?partial=1").text
    assert '<li class="clip">' in html
    assert "<html" not in html and 'class="sidebar"' not in html and 'id="sheet-clip"' not in html
    assert auth_client.get("/clipboard?partial=1").headers["cache-control"] == "no-store"


def test_list_page_has_the_sheet_and_delete_confirm(auth_client):
    create(auth_client, title="t")
    html = auth_client.get("/clipboard").text
    assert 'id="sheet-clip"' in html and 'id="modal-delete"' in html
    for action in ("edit", "favorite", "hide", "delete"):
        assert f'data-action="{action}"' in html


def test_editor_dates_are_in_the_vault_timezone(auth_client, settings):
    clip = create(auth_client, title="t")
    set_updated_at(settings, clip["id"], "2024-03-01T20:00:00Z")  # 01:30 on Mar 2 in Asia/Kolkata
    assert "Saved · Mar 2, 2024<" in auth_client.get(f"/clipboard/{clip['id']}").text
