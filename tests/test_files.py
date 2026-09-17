import logging
import re
from urllib.parse import quote

import pytest

from app import db, storage
from tests.test_security import assert_no_inline

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4


def upload(client, name, data=b"hello vault", expect=201):
    r = client.post("/api/files", content=data,
                    headers={"Content-Type": "application/octet-stream", "X-File-Name": quote(name)})
    assert r.status_code == expect, r.text
    return r.json()


def disk_files(settings):
    return sorted(p for p in settings.files_dir.rglob("*") if p.is_file())


# ---- storage helpers -------------------------------------------------------------------

@pytest.mark.parametrize("raw, clean", [
    ("../../etc/passwd", "passwd"),
    ("..\\..\\boot.ini", "boot.ini"),
    ("a\x00b.txt", "ab.txt"),
    ("   ", "unnamed"),
    ("", "unnamed"),
    ("...", "unnamed"),
    (" .hidden. ", "hidden"),
    ("line\nbreak\r\t.pdf", "linebreak.pdf"),
    ("photo‮gpj.exe", "photogpj.exe"),
    ("रसीद.pdf", "रसीद.pdf"),
    ("x" * 300, "x" * 255),
    ("y" * 300 + ".pdf", "y" * 251 + ".pdf"),
])
def test_clean_name(raw, clean):
    assert storage.clean_name(raw) == clean


def test_path_for_only_accepts_generated_ids(tmp_path):
    good = "ab" + "0" * 30
    assert storage.path_for(tmp_path, good) == (tmp_path / "ab" / good).resolve()
    for bad in ("../" + "a" * 29, "A" * 32, "a" * 31, "a" * 33, "", "../../etc/passwd", "a" * 31 + "/"):
        with pytest.raises(ValueError):
            storage.path_for(tmp_path, bad)


def test_types():
    assert storage.kind_and_mime("IMG_0421.JPG") == ("image", "image/jpeg")
    assert storage.kind_and_mime("clip.mov") == ("video", "video/quicktime")
    assert storage.kind_and_mime("scan.pdf") == ("pdf", "application/pdf")
    assert storage.kind_and_mime("page.html") == ("other", "text/html")
    assert storage.kind_and_mime("noext") == ("other", "application/octet-stream")
    for name in ("a.html", "a.svg", "a.xml", "a.js", "a.htm", "a.exe", "a"):
        assert storage.inline_type(name) is None
    assert storage.inline_type("notes.md") == "text/plain; charset=utf-8"


# ---- Upload ----------------------------------------------------------------------------

def test_upload_then_download_identical_bytes(auth_client, settings):
    data = bytes(range(256)) * 5000  # 1.28 MB, more than one chunk
    file = upload(auth_client, "big.bin", data)
    assert set(file) == {"id", "folder_id", "name", "size", "mime", "kind", "favorite", "created_at", "updated_at"}
    assert re.fullmatch(r"[0-9a-f]{32}", file["id"])
    assert (file["name"], file["size"], file["folder_id"], file["kind"]) == ("big.bin", len(data), None, "other")
    r = auth_client.get(f"/api/files/{file['id']}/download")
    assert r.status_code == 200 and r.content == data
    assert r.headers["content-disposition"] == 'attachment; filename="big.bin"'
    with db.connect(settings.db_path) as conn:
        import hashlib
        assert conn.execute("SELECT sha256 FROM files").fetchone()[0] == hashlib.sha256(data).hexdigest()


def test_many_files_one_request_each(auth_client, settings):
    """TECH_PLAN §9: one raw-body request per file instead of one multipart batch."""
    names = ["a.txt", "b.jpg", "c.pdf", "d.mp4", "e.zip"]
    for name in names:
        upload(auth_client, name, name.encode())
    listed = auth_client.get("/api/files").json()
    assert listed["folders"] == []
    assert [f["name"] for f in listed["files"]] == names  # a folder starts sorted by name (S7)
    assert len(disk_files(settings)) == 5


@pytest.mark.parametrize("raw, shown", [
    ("../../etc/passwd", "passwd"), ("..\\..\\boot.ini", "boot.ini"), ("a\x00b.txt", "ab.txt"),
    ("   ", "unnamed"), ("n" * 300, "n" * 255),
])
def test_hostile_names_stored_safely(auth_client, settings, raw, shown):
    file = upload(auth_client, raw)
    assert file["name"] == shown
    [path] = disk_files(settings)
    assert path == settings.files_dir.resolve() / file["id"][:2] / file["id"]
    assert path.resolve().is_relative_to(settings.files_dir.resolve())
    assert not (settings.data_dir.parent / "etc").exists()
    assert shown in auth_client.get("/files").text


def test_missing_name_header(auth_client):
    r = auth_client.post("/api/files", content=b"x", headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 201 and r.json()["name"] == "unnamed"


def test_unicode_name_downloads_with_filename_star(auth_client):
    file = upload(auth_client, "रसीद.pdf", b"%PDF-1.4")
    r = auth_client.get(f"/api/files/{file['id']}/download")
    assert r.headers["content-disposition"] == "attachment; filename*=utf-8''" + quote("रसीद.pdf")


def test_too_large_is_rejected_and_leaves_nothing(auth_client, settings):
    r = auth_client.post("/api/files", content=b"x" * (3 * 1024 * 1024),
                         headers={"Content-Type": "application/octet-stream", "X-File-Name": "big.bin"})
    assert r.status_code == 413
    assert r.json() == {"error": "Too large (max 2 MB)"}
    assert list((settings.data_dir / "tmp").iterdir()) == []
    assert disk_files(settings) == []
    assert auth_client.get("/api/files").json()["files"] == []


def test_body_longer_than_declared_is_rejected_while_streaming(app, auth_client, settings):
    def body():
        yield b"x" * 1024 * 1024
        yield b"x" * 1024 * 1024
        yield b"x" * 1024 * 1024

    # A generator body has no Content-Length: refused before reading.
    r = auth_client.post("/api/files", content=body(), headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 411
    # Lie about the length: stopped as soon as the stream passes it.
    r = auth_client.post("/api/files", content=body(),
                         headers={"Content-Type": "application/octet-stream", "Content-Length": "100"})
    assert r.status_code == 413
    assert list((settings.data_dir / "tmp").iterdir()) == []
    assert disk_files(settings) == []


def test_disk_full(auth_client, settings, monkeypatch):
    monkeypatch.setattr(storage, "DISK_RESERVE", 10**18)
    r = auth_client.post("/api/files", content=b"x", headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 507 and r.json() == {"error": "Vault disk full"}
    assert disk_files(settings) == []


def test_failed_insert_removes_the_moved_file(auth_client, settings, monkeypatch):
    from app import files

    def broken(*args):
        raise RuntimeError("db down")

    monkeypatch.setattr(files, "insert_file", broken)
    auth_client.app  # noqa: B018
    with pytest.raises(RuntimeError):
        upload(auth_client, "a.txt")
    assert disk_files(settings) == []


def test_upload_needs_octet_stream_and_same_origin(auth_client, settings):
    r = auth_client.post("/api/files", content=b"x", headers={"Content-Type": "text/html", "X-File-Name": "a.html"})
    assert r.status_code == 415
    r = auth_client.post("/api/files", content=b"x",
                         headers={"Content-Type": "application/octet-stream", "Origin": "https://evil.example"})
    assert r.status_code == 403
    assert disk_files(settings) == []


def test_logs_hold_ids_not_names(auth_client, caplog):
    with caplog.at_level(logging.DEBUG):
        file = upload(auth_client, "passport-scan.pdf")
        auth_client.patch(f"/api/files/{file['id']}", json={"name": "renamed-secret.pdf"})
        auth_client.delete(f"/api/files/{file['id']}")
    assert "passport" not in caplog.text and "renamed-secret" not in caplog.text
    assert f"File {file['id']} uploaded" in caplog.text


# ---- Serving ---------------------------------------------------------------------------

def test_view_serves_safe_types_inline_with_a_sandbox(auth_client):
    png = upload(auth_client, "photo.png", PNG)
    r = auth_client.get(f"/api/files/{png['id']}/view")
    assert r.status_code == 200 and r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["content-disposition"] == 'inline; filename="photo.png"'
    assert r.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "private, no-cache"

    text = upload(auth_client, "readme.md", "# hi <script>".encode())
    r = auth_client.get(f"/api/files/{text['id']}/view")
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert r.headers["content-disposition"].startswith("inline;")


@pytest.mark.parametrize("name", ["page.html", "logo.svg", "feed.xml", "app.js", "PAGE.HTM", "tool.exe", "noext"])
def test_active_content_is_never_inline(auth_client, name):
    file = upload(auth_client, name, b"<html><script>alert(1)</script></html>")
    r = auth_client.get(f"/api/files/{file['id']}/view")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment;")
    assert r.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_pdf_can_be_framed_by_the_vault_only(auth_client):
    file = upload(auth_client, "scan.pdf", b"%PDF-1.4 test")
    r = auth_client.get(f"/api/files/{file['id']}/view")
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'self'"
    r = auth_client.get(f"/api/files/{file['id']}/download")
    assert r.headers["x-frame-options"] == "DENY" and "sandbox" in r.headers["content-security-policy"]


@pytest.mark.parametrize("endpoint", ["view", "download"])
def test_range_requests(auth_client, endpoint):
    data = bytes(range(256)) * 10
    file = upload(auth_client, "clip.mp4", data)
    url = f"/api/files/{file['id']}/{endpoint}"
    assert auth_client.get(url).headers["accept-ranges"] == "bytes"
    r = auth_client.get(url, headers={"Range": "bytes=10-19"})
    assert r.status_code == 206
    assert r.content == data[10:20]
    assert r.headers["content-range"] == f"bytes 10-19/{len(data)}"
    r = auth_client.get(url, headers={"Range": "bytes=-5"})
    assert r.status_code == 206 and r.content == data[-5:]
    assert auth_client.get(url, headers={"Range": "bytes=99999-"}).status_code == 416


@pytest.mark.parametrize("file_id", ["x" * 32, "0" * 32, "..%2F..%2Fvault.db", "abc"])
def test_unknown_ids_are_404(auth_client, file_id):
    for method, path in [("GET", f"/api/files/{file_id}/view"), ("GET", f"/api/files/{file_id}/download"),
                         ("DELETE", f"/api/files/{file_id}")]:
        assert auth_client.request(method, path).status_code == 404
    assert auth_client.patch(f"/api/files/{file_id}", json={"favorite": True}).status_code == 404


def test_row_without_bytes_is_404_not_500(auth_client, settings):
    file = upload(auth_client, "a.txt")
    storage.path_for(settings.files_dir, file["id"]).unlink()
    r = auth_client.get(f"/api/files/{file['id']}/download")
    assert r.status_code == 404 and r.json() == {"error": "This file is missing from the vault's disk."}


# ---- Rename, favorite, delete ------------------------------------------------------------

def test_rename(auth_client, settings):
    file = upload(auth_client, "IMG_0001.jpg", PNG)
    url = f"/api/files/{file['id']}"
    r = auth_client.patch(url, json={"name": "../passport.pdf"})
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["kind"], r.json()["mime"]) == ("passport.pdf", "pdf", "application/pdf")
    assert r.json()["updated_at"] >= file["updated_at"]
    [path] = disk_files(settings)
    assert path.name == file["id"]  # the bytes never move
    for bad in ("", "  ", " . ", 5):
        r = auth_client.patch(url, json={"name": bad})
        assert r.status_code == 422
    assert auth_client.patch(url, json={"name": "  "}).json() == {"error": "Enter a name."}
    assert auth_client.patch(url, json={"size": 1}).status_code == 422
    assert auth_client.get("/api/files").json()["files"][0]["name"] == "passport.pdf"


def test_favorite(auth_client):
    file = upload(auth_client, "a.txt")
    r = auth_client.patch(f"/api/files/{file['id']}", json={"favorite": True})
    assert r.json()["favorite"] is True
    assert r.json()["updated_at"] == file["updated_at"]
    assert auth_client.patch(f"/api/files/{file['id']}", json={"favorite": "yes"}).status_code == 422


def test_delete_removes_row_and_bytes(auth_client, settings):
    file = upload(auth_client, "a.txt")
    assert len(disk_files(settings)) == 1
    assert auth_client.delete(f"/api/files/{file['id']}").status_code == 204
    assert disk_files(settings) == []
    assert auth_client.get("/api/files").json()["files"] == []
    r = auth_client.delete(f"/api/files/{file['id']}")
    assert r.status_code == 404 and r.json() == {"error": "That file no longer exists."}


def test_delete_with_bytes_already_gone(auth_client, settings, caplog):
    file = upload(auth_client, "tax-secret.pdf")
    storage.path_for(settings.files_dir, file["id"]).unlink()
    with caplog.at_level(logging.WARNING):
        assert auth_client.delete(f"/api/files/{file['id']}").status_code == 204
    assert auth_client.get("/api/files").json()["files"] == []
    assert file["id"] in caplog.text and "tax-secret" not in caplog.text


# ---- Logged out ------------------------------------------------------------------------

@pytest.mark.parametrize("method, path", [
    ("GET", "/files"), ("GET", "/api/files"), ("POST", "/api/files"), ("PATCH", "/api/files/" + "a" * 32),
    ("DELETE", "/api/files/" + "a" * 32), ("GET", "/api/files/" + "a" * 32 + "/view"),
    ("GET", "/api/files/" + "a" * 32 + "/download"),
])
def test_logged_out(client, settings, method, path):
    kwargs = {}
    if method == "POST":
        kwargs = {"content": b"x", "headers": {"Content-Type": "application/octet-stream"}}
    elif method == "PATCH":
        kwargs = {"json": {}}
    r = client.request(method, path, follow_redirects=False, **kwargs)
    if path.startswith("/api/"):
        assert r.status_code == 401
    else:
        assert r.status_code == 302
    assert disk_files(settings) == []


# ---- Page ------------------------------------------------------------------------------

def test_files_page(auth_client):
    assert "No files yet." in auth_client.get("/files").text
    file = upload(auth_client, "electricity-bill-aug.pdf", b"%PDF")
    auth_client.patch(f"/api/files/{file['id']}", json={"favorite": True})
    html = auth_client.get("/files").text
    [row] = re.findall(r'<li class="row" data-name="electricity-bill-aug.pdf">.*?</li>', html, re.S)
    assert '<span class="name__head">electricity-bill</span><span class="name__tail">-aug.pdf</span>' in row
    assert f'href="/api/files/{file["id"]}/view"' in row
    assert "4 B · Just now" in row
    assert "icon--file-text" in row and 'class="pin-mark"' in row
    assert f'data-download="/api/files/{file["id"]}/download"' in row
    assert 'data-copy="electricity-bill-aug.pdf"' in row and 'data-rename="electricity-bill-aug.pdf"' in row
    assert "1 file · 4 B" in html
    assert 'id="modal-rename"' in html and 'id="sheet-file"' in html
    assert_no_inline(html)
    partial = auth_client.get("/files?partial=1").text
    assert "<html" not in partial and "data-refresh-after-upload" in partial


def test_names_are_escaped(auth_client):
    upload(auth_client, '<img src=x onerror=alert(1)>".png', PNG)
    html = auth_client.get("/files").text
    assert "<img src=x" not in html
    assert_no_inline(html)
