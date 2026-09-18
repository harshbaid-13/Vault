import re
import uuid

import pytest

from app import db, files
from tests.test_files import upload
from tests.test_security import assert_no_inline
from tests.test_thumbs import png


def add_rows(settings, specs):
    """Insert file rows directly (no bytes): [(name, created_at)]. Returns their ids in order."""
    ids = []
    with db.connect(settings.db_path) as conn:
        for name, created in specs:
            file_id = uuid.uuid4().hex
            files.insert_file(conn, file_id, name, 100, "0" * 64)
            conn.execute("UPDATE files SET created_at = ? WHERE id = ?", (created, file_id))
            ids.append(file_id)
    return ids


def tile_ids(html):
    return re.findall(r'class="photo-tile" href="/photos/([0-9a-f]{32})"', html)


# ---- Photos grid -------------------------------------------------------------------------

def test_grid_has_images_and_videos_newest_first_by_month(auth_client, settings):
    ids = add_rows(settings, [
        ("aug.jpg", "2026-08-20T10:00:00Z"), ("sep-old.png", "2026-09-01T10:00:00Z"),
        ("sep-new.mp4", "2026-09-10T10:00:00Z"), ("doc.pdf", "2026-09-11T10:00:00Z"),
        ("notes.txt", "2026-09-12T10:00:00Z"),
    ])
    html = auth_client.get("/photos").text
    assert tile_ids(html) == [ids[2], ids[1], ids[0]]
    assert html.index("September 2026") < html.index("August 2026")
    assert "photos__more" not in html
    [video] = re.findall(r'<a class="photo-tile" href="/photos/' + ids[2] + '".*?</a>', html, re.S)
    assert 'aria-label="Video sep-new.mp4"' in video and "photo-tile__badge" in video and "<img" not in video
    [image] = re.findall(r'<a class="photo-tile" href="/photos/' + ids[1] + '".*?</a>', html, re.S)
    assert f'src="/api/files/{ids[1]}/thumb"' in image and 'loading="lazy"' in image and "data-thumb" in image
    assert_no_inline(html)


def test_month_uses_the_vault_timezone(auth_client, settings):
    add_rows(settings, [("new-year.jpg", "2025-12-31T20:00:00Z")])  # 01:30 on Jan 1 in Kolkata
    assert "January 2026" in auth_client.get("/photos").text


def test_pagination(auth_client, settings):
    specs = [(f"p{n:03}.jpg", f"2026-09-01T10:{n // 60:02}:{n % 60:02}Z") for n in range(130)]
    # Two photos at the same second: the id breaks the tie, so none is skipped or repeated.
    specs.append(("same-second.jpg", specs[70][1]))
    add_rows(settings, specs)
    seen = []
    html = auth_client.get("/photos").text
    pages = 0
    while True:
        pages += 1
        page = tile_ids(html)
        assert len(page) <= 60
        seen += page
        more = re.search(r'href="/photos\?before=([^"]+)" data-photos-more', html)
        if not more:
            break
        html = auth_client.get(f"/photos?before={more[1]}&partial=1").text
        assert "<html" not in html
    assert pages == 3 and len(seen) == 131 and len(set(seen)) == 131
    with db.connect(settings.db_path) as conn:
        expected = [row[0] for row in conn.execute("SELECT id FROM files ORDER BY created_at DESC, id DESC")]
    assert seen == expected


@pytest.mark.parametrize("before", ["x", "2026-09-01T10:00:00Z", "2026-09-01T10:00:00Z,../../etc", "1,2"])
def test_bad_cursor_is_404(auth_client, before):
    assert auth_client.get("/photos", params={"before": before}).status_code == 404


def test_empty(auth_client):
    assert "No photos yet." in auth_client.get("/photos").text


# ---- Viewer ------------------------------------------------------------------------------

def test_viewer_with_neighbours(auth_client, settings):
    ids = add_rows(settings, [(f"p{n:02}.jpg", f"2026-09-01T10:00:{n:02}Z") for n in range(30)])
    newest_first = list(reversed(ids))
    middle = newest_first[15]
    r = auth_client.get(f"/photos/{middle}")
    assert r.status_code == 200
    html = r.text
    slides = re.findall(r'class="viewer__slide" data-id="([0-9a-f]{32})"', html)
    assert slides == newest_first[5:26]
    assert "data-more-newer" in html and "data-more-older" in html
    assert f'data-id="{middle}" data-name="p14.jpg" data-current' in html
    assert f'<img class="viewer__img" src="/api/files/{middle}/view"' in html
    assert 'class="tabbar"' not in html and 'class="sidebar"' not in html
    assert 'data-action="copy-link"' in html and 'id="modal-delete"' in html
    assert_no_inline(html)
    edge = auth_client.get(f"/photos/{newest_first[0]}").text
    assert "data-more-newer" not in edge and "data-more-older" in edge
    assert re.findall(r'class="viewer__slide" data-id="([0-9a-f]{32})"', edge) == newest_first[:11]


def test_viewer_slides_by_kind(auth_client):
    video = upload(auth_client, "clip.mp4", b"\x00" * 10)
    heic = upload(auth_client, "IMG_0001.heic", b"x")
    html = auth_client.get(f"/photos/{video['id']}").text
    assert f'<video class="viewer__media" src="/api/files/{video["id"]}/view" controls playsinline preload="none">' in html
    [slide] = re.findall(r'data-id="' + heic["id"] + '".*?</figure>', html, re.S)
    assert "No preview for this type." in slide and "<img" not in slide


@pytest.mark.parametrize("name", ["scan.pdf", "notes.txt"])
def test_viewer_only_for_photos_and_videos(auth_client, name):
    file = upload(auth_client, name)
    assert auth_client.get(f"/photos/{file['id']}").status_code == 404
    assert auth_client.get("/photos/" + "0" * 32).status_code == 404
    assert auth_client.get("/photos/nope").status_code == 404


def test_names_escaped(auth_client):
    file = upload(auth_client, '<img src=x onerror=alert(1)>.png', png())
    for path in ("/photos", f"/photos/{file['id']}", f"/files/{file['id']}"):
        html = auth_client.get(path).text
        assert "<img src=x" not in html
        assert_no_inline(html)


# ---- Preview page -------------------------------------------------------------------------

@pytest.mark.parametrize("name, data, expect, absent", [
    ("photo.png", png(), '<img class="preview__img" src="/api/files/{id}/view"', "No preview"),
    ("scan.pdf", b"%PDF-1.4", 'data-pdf-src="/api/files/{id}/view"', "No preview"),
    ("clip.mp4", b"\x00", '<video class="preview__video" src="/api/files/{id}/view" controls playsinline preload="metadata">', "No preview"),
    ("song.mp3", b"\x00", '<audio class="preview__audio" src="/api/files/{id}/view" controls', "No preview"),
    ("notes.md", b"# Title\n<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;", "No preview"),
    ("page.html", b"<script>alert(1)</script>", "No preview for this type.", "/view"),
    ("logo.svg", b"<svg onload=alert(1)>", "No preview for this type.", "/view"),
    ("IMG_1.heic", b"x", "No preview for this type.", "preview__img"),
    ("archive.zip", b"PK", "No preview for this type.", "/view"),
])
def test_preview_page_per_type(auth_client, name, data, expect, absent):
    file = upload(auth_client, name, data)
    r = auth_client.get(f"/files/{file['id']}")
    assert r.status_code == 200
    html = r.text
    assert expect.format(id=file["id"]) in html
    assert absent not in html.split('<main')[1].split("</main>")[0]
    assert f'href="/api/files/{file["id"]}/download" download' in html
    assert f'<span>{name}</span>' in html and f'data-copy="{name}"' in html
    assert 'data-action="move"' in html and 'data-action="rename"' in html and 'data-action="delete"' in html
    assert f'data-star data-item="/api/files/{file["id"]}"' in html
    assert 'data-after-delete="/files"' in html
    assert_no_inline(html)


def test_preview_text_details(auth_client):
    file = upload(auth_client, "wifi.txt", "पासवर्ड: hunter2".encode())
    html = auth_client.get(f"/files/{file['id']}").text
    assert '<pre class="preview__text" id="preview-text">पासवर्ड: hunter2</pre>' in html
    assert 'data-copy-from="#preview-text"' in html
    assert "TXT · " in html and "Added Today" in html
    big = upload(auth_client, "big.log", b"x" * (1024 * 1024 + 1))
    html = auth_client.get(f"/files/{big['id']}").text
    assert "preview__text" not in html and "No preview for this type." in html


def test_preview_pdf_has_open_button(auth_client):
    file = upload(auth_client, "scan.pdf", b"%PDF-1.4")
    html = auth_client.get(f"/files/{file['id']}").text
    assert f'href="/api/files/{file["id"]}/view" target="_blank" rel="noopener">Open PDF' in html
    assert "<iframe" in html and " src=" not in html.split("<iframe")[1].split(">")[0]


def test_preview_in_folder_and_missing_bytes(auth_client, settings):
    from app import storage
    from tests.test_folders import make, upload_into
    folder = make(auth_client, "Bills")
    file = upload_into(auth_client, folder["id"], "power.pdf", b"%PDF")
    html = auth_client.get(f"/files/{file['id']}").text
    assert f'href="/files?folder={folder["id"]}" aria-label="Back to Bills"' in html
    assert f'data-folder-id="{folder["id"]}"' in html
    storage.path_for(settings.files_dir, file["id"]).unlink()
    r = auth_client.get(f"/files/{file['id']}")
    assert r.status_code == 200 and "missing from the vault" in r.text
    assert "<html" not in auth_client.get(f"/files/{file['id']}?partial=1").text


@pytest.mark.parametrize("file_id", ["0" * 32, "nope", "A" * 32])
def test_preview_unknown_is_404_page(auth_client, file_id):
    r = auth_client.get(f"/files/{file_id}")
    assert r.status_code == 404 and "<html" in r.text


# ---- Logged out --------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/photos", "/photos/" + "a" * 32, "/files/" + "a" * 32])
def test_logged_out(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == 302
