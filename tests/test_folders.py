import logging
import re

import pytest

from app import db
from tests.test_files import disk_files, upload
from tests.test_security import assert_no_inline

FOLDER_FIELDS = {"id", "parent_id", "name", "sort", "created_at", "updated_at"}


def make(client, name, parent_id=None, expect=201):
    r = client.post("/api/folders", json={"name": name, "parent_id": parent_id})
    assert r.status_code == expect, r.text
    return r.json()


def upload_into(client, folder_id, name, data=b"hello vault", expect=201):
    from urllib.parse import quote
    r = client.post(f"/api/files?folder_id={folder_id}", content=data,
                    headers={"Content-Type": "application/octet-stream", "X-File-Name": quote(name)})
    assert r.status_code == expect, r.text
    return r.json()


def contents(client, folder_id=None, sort=None):
    params = {}
    if folder_id is not None:
        params["folder_id"] = folder_id
    if sort:
        params["sort"] = sort
    body = client.get("/api/files", params=params).json()
    return [f["name"] for f in body["folders"]], [f["name"] for f in body["files"]]


# ---- Create, rename --------------------------------------------------------------------

def test_create_nested(auth_client):
    docs = make(auth_client, "Documents")
    assert set(docs) == FOLDER_FIELDS
    assert (docs["name"], docs["parent_id"], docs["sort"]) == ("Documents", None, "name")
    bills = make(auth_client, "Bills", docs["id"])
    year = make(auth_client, "2026", bills["id"])
    assert year["parent_id"] == bills["id"]
    assert contents(auth_client) == (["Documents"], [])
    assert contents(auth_client, docs["id"]) == (["Bills"], [])
    tree = auth_client.get("/api/folders").json()["folders"]
    assert [f["name"] for f in tree] == ["2026", "Bills", "Documents"]


def test_names_are_cleaned_like_filenames(auth_client):
    assert make(auth_client, "  ../../etc/Tax 2025. ")["name"] == "Tax 2025"
    assert make(auth_client, "a\x00b")["name"] == "ab"
    assert len(make(auth_client, "x" * 300)["name"]) == 255


def test_duplicate_name_rejected_case_insensitive(auth_client):
    docs = make(auth_client, "Documents")
    r = auth_client.post("/api/folders", json={"name": "documents", "parent_id": None})
    assert r.status_code == 409 and r.json() == {"error": "There's already a folder called “documents” there."}
    # Same name under a different parent is fine.
    make(auth_client, "Documents", docs["id"])
    other = make(auth_client, "Other")
    r = auth_client.patch(f"/api/folders/{other['id']}", json={"name": "DOCUMENTS"})
    assert r.status_code == 409


def test_rename(auth_client):
    folder = make(auth_client, "Tax")
    r = auth_client.patch(f"/api/folders/{folder['id']}", json={"name": "Tax 2026"})
    assert r.status_code == 200 and r.json()["name"] == "Tax 2026"
    assert r.json()["updated_at"] >= folder["updated_at"]
    # Renaming to its own name in another case is not a clash with itself.
    assert auth_client.patch(f"/api/folders/{folder['id']}", json={"name": "TAX 2026"}).status_code == 200


@pytest.mark.parametrize("body, status, error", [
    ({"name": ""}, 422, "Enter a name."),
    ({"name": " . "}, 422, "Enter a name."),
    ({}, 422, "Enter a name."),
    ({"name": 5}, 422, "That request wasn't understood."),
    ({"name": "a", "parent_id": "1"}, 422, "That request wasn't understood."),
    ({"name": "a", "parent_id": True}, 422, "That request wasn't understood."),
    ({"name": "a", "parent_id": 0}, 422, "That request wasn't understood."),
    ({"name": "a", "color": "red"}, 422, "That request wasn't understood."),
    ({"name": "a", "parent_id": 999}, 404, "That folder no longer exists."),
])
def test_create_validation(auth_client, body, status, error):
    r = auth_client.post("/api/folders", json=body)
    assert (r.status_code, r.json()) == (status, {"error": error})


def test_missing_folder_is_404(auth_client):
    for method, path in [("PATCH", "/api/folders/999"), ("DELETE", "/api/folders/999"),
                         ("GET", "/api/folders/999/summary"), ("GET", "/api/files?folder_id=999")]:
        r = auth_client.request(method, path, json={"name": "x"} if method == "PATCH" else None)
        assert r.status_code == 404 and r.json() == {"error": "That folder no longer exists."}
    assert auth_client.get("/api/folders/abc/summary").status_code == 404


# ---- Move ------------------------------------------------------------------------------

def test_nested_move(auth_client):
    a = make(auth_client, "A")
    b = make(auth_client, "B")
    c = make(auth_client, "C", b["id"])
    file = upload_into(auth_client, c["id"], "deep.txt")
    r = auth_client.patch(f"/api/folders/{b['id']}", json={"parent_id": a["id"]})
    assert r.status_code == 200 and r.json()["parent_id"] == a["id"]
    assert contents(auth_client) == (["A"], [])
    assert contents(auth_client, a["id"]) == (["B"], [])
    assert contents(auth_client, c["id"]) == ([], ["deep.txt"])
    # Back to the top level.
    assert auth_client.patch(f"/api/folders/{b['id']}", json={"parent_id": None}).json()["parent_id"] is None
    assert auth_client.get(f"/api/files/{file['id']}/download").content == b"hello vault"


def test_move_into_itself_or_own_child_rejected(auth_client):
    a = make(auth_client, "A")
    b = make(auth_client, "B", a["id"])
    c = make(auth_client, "C", b["id"])
    for target in (a, b, c):
        r = auth_client.patch(f"/api/folders/{a['id']}", json={"parent_id": target["id"]})
        assert r.status_code == 422 and r.json() == {"error": "A folder can't go inside itself."}
        r = auth_client.post("/api/move", json={"files": [], "folders": [a["id"]], "to": target["id"]})
        assert r.status_code == 422
    assert contents(auth_client) == (["A"], [])


def test_bulk_move(auth_client, settings):
    docs = make(auth_client, "Documents")
    old = make(auth_client, "Old")
    files = [upload(auth_client, f"bill-{n}.pdf") for n in range(5)]
    before = disk_files(settings)
    r = auth_client.post("/api/move", json={"files": [f["id"] for f in files], "folders": [old["id"]], "to": docs["id"]})
    assert r.status_code == 200 and r.json() == {"moved": 6}
    assert contents(auth_client) == (["Documents"], [])
    assert contents(auth_client, docs["id"]) == (["Old"], [f"bill-{n}.pdf" for n in range(5)])
    assert disk_files(settings) == before  # bytes never move
    r = auth_client.post("/api/move", json={"files": [files[0]["id"]], "folders": [], "to": None})
    assert r.json() == {"moved": 1}
    assert contents(auth_client) == (["Documents"], ["bill-0.pdf"])


def test_bulk_move_is_all_or_nothing(auth_client):
    dest = make(auth_client, "Dest")
    make(auth_client, "Bills", dest["id"])
    bills = make(auth_client, "Bills")
    file = upload(auth_client, "a.txt")
    r = auth_client.post("/api/move", json={"files": [file["id"]], "folders": [bills["id"]], "to": dest["id"]})
    assert r.status_code == 409 and r.json() == {"error": "There's already a folder called “Bills” there."}
    assert contents(auth_client) == (["Bills", "Dest"], ["a.txt"])
    r = auth_client.post("/api/move", json={"files": [file["id"], "f" * 32], "folders": [], "to": dest["id"]})
    assert r.status_code == 404
    assert contents(auth_client) == (["Bills", "Dest"], ["a.txt"])
    r = auth_client.post("/api/move", json={"files": [file["id"]], "folders": [], "to": 999})
    assert r.status_code == 404 and r.json() == {"error": "That folder no longer exists."}


@pytest.mark.parametrize("body, error", [
    ({"files": [], "folders": [], "to": None}, "Select something first."),
    ({"files": [], "folders": [1]}, "That request wasn't understood."),
    ({"files": "abc", "folders": [], "to": None}, "That request wasn't understood."),
    ({"files": ["../../etc"], "folders": [], "to": None}, "That request wasn't understood."),
    ({"files": [], "folders": ["1"], "to": None}, "That request wasn't understood."),
    ({"files": [], "folders": [True], "to": None}, "That request wasn't understood."),
    ({"files": [], "folders": [1], "to": "1"}, "That request wasn't understood."),
    ({"files": [], "folders": [1], "to": None, "copy": True}, "That request wasn't understood."),
    ({"files": [], "folders": list(range(1, 1002)), "to": None}, "That's too many items at once (max 1,000)."),
])
def test_move_validation(auth_client, body, error):
    r = auth_client.post("/api/move", json=body)
    assert (r.status_code, r.json()) == (422, {"error": error})


def test_patch_file_folder(auth_client):
    folder = make(auth_client, "Photos")
    file = upload(auth_client, "a.jpg")
    r = auth_client.patch(f"/api/files/{file['id']}", json={"folder_id": folder["id"]})
    assert r.status_code == 200 and r.json()["folder_id"] == folder["id"]
    assert r.json()["updated_at"] == file["updated_at"]
    assert auth_client.patch(f"/api/files/{file['id']}", json={"folder_id": 999}).status_code == 404
    assert auth_client.patch(f"/api/files/{file['id']}", json={"folder_id": "1"}).status_code == 422
    assert auth_client.patch(f"/api/files/{file['id']}", json={"folder_id": None}).json()["folder_id"] is None


# ---- Delete ----------------------------------------------------------------------------

def test_recursive_delete_removes_disk_files(auth_client, settings):
    a = make(auth_client, "A")
    b = make(auth_client, "B", a["id"])
    c = make(auth_client, "C", b["id"])
    upload_into(auth_client, a["id"], "1.txt", b"12345")
    upload_into(auth_client, b["id"], "2.txt", b"123")
    upload_into(auth_client, c["id"], "3.txt", b"1")
    keep = upload(auth_client, "keep.txt")
    other = make(auth_client, "Other")
    assert len(disk_files(settings)) == 4
    assert auth_client.get(f"/api/folders/{a['id']}/summary").json() == {"folders": 2, "files": 3, "size": 9}
    assert auth_client.get(f"/api/folders/{c['id']}/summary").json() == {"folders": 0, "files": 1, "size": 1}
    assert auth_client.delete(f"/api/folders/{a['id']}").status_code == 204
    assert disk_files(settings) == [settings.files_dir.resolve() / keep["id"][:2] / keep["id"]]
    assert contents(auth_client) == (["Other"], ["keep.txt"])
    with db.connect(settings.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM folders").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 1
    assert auth_client.delete(f"/api/folders/{a['id']}").status_code == 404
    assert auth_client.get(f"/api/folders/{other['id']}/summary").json() == {"folders": 0, "files": 0, "size": 0}


def test_bulk_delete(auth_client, settings):
    a = make(auth_client, "A")
    make(auth_client, "Inner", a["id"])
    upload_into(auth_client, a["id"], "in-a.txt")
    loose = [upload(auth_client, f"{n}.txt") for n in range(3)]
    r = auth_client.post("/api/delete", json={"files": [loose[0]["id"], loose[1]["id"], "0" * 32], "folders": [a["id"], 999]})
    assert r.status_code == 200 and r.json() == {"deleted": {"folders": 2, "files": 3}}
    assert contents(auth_client) == ([], ["2.txt"])
    assert len(disk_files(settings)) == 1
    r = auth_client.post("/api/delete", json={"files": [], "folders": []})
    assert (r.status_code, r.json()) == (422, {"error": "Select something first."})


# ---- Uploads into a folder ----------------------------------------------------------------

def test_upload_into_folder(auth_client, settings):
    bills = make(auth_client, "Bills")
    file = upload_into(auth_client, bills["id"], "power.pdf", b"%PDF")
    assert file["folder_id"] == bills["id"]
    assert contents(auth_client) == (["Bills"], [])
    assert contents(auth_client, bills["id"]) == ([], ["power.pdf"])
    # A folder that doesn't exist is refused before any bytes are stored.
    for bad in ("999", "abc", "-1", "1.5"):
        r = auth_client.post(f"/api/files?folder_id={bad}", content=b"x",
                             headers={"Content-Type": "application/octet-stream"})
        assert r.status_code == 404 and r.json() == {"error": "That folder no longer exists."}
    assert len(disk_files(settings)) == 1
    assert list((settings.data_dir / "tmp").iterdir()) == []


def test_upload_into_folder_deleted_meanwhile(auth_client, settings, monkeypatch):
    from app import files, folders
    bills = make(auth_client, "Bills")
    real = files.insert_file

    def delete_first(conn, *args):
        conn.execute("DELETE FROM folders")
        return real(conn, *args)

    monkeypatch.setattr(files, "insert_file", delete_first)
    r = auth_client.post(f"/api/files?folder_id={bills['id']}", content=b"x",
                         headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 404 and r.json() == {"error": folders.NOT_FOUND}
    assert disk_files(settings) == []


# ---- Sorting ---------------------------------------------------------------------------

def set_created(settings, name, stamp):
    with db.connect(settings.db_path) as conn:
        conn.execute("UPDATE files SET created_at = ? WHERE name = ?", (stamp, name))
        conn.execute("UPDATE folders SET created_at = ? WHERE name = ?", (stamp, name))


def test_sort_order(auth_client, settings):
    upload(auth_client, "b.pdf", b"x" * 30)
    upload(auth_client, "A.txt", b"x" * 10)
    upload(auth_client, "c.jpg", b"x" * 20)
    make(auth_client, "zeta")
    make(auth_client, "Alpha")
    set_created(settings, "b.pdf", "2026-01-01T00:00:00Z")
    set_created(settings, "A.txt", "2026-03-01T00:00:00Z")
    set_created(settings, "c.jpg", "2026-02-01T00:00:00Z")
    set_created(settings, "zeta", "2026-01-01T00:00:00Z")
    set_created(settings, "Alpha", "2026-02-01T00:00:00Z")
    expected = {
        "name": (["Alpha", "zeta"], ["A.txt", "b.pdf", "c.jpg"]),
        "-name": (["zeta", "Alpha"], ["c.jpg", "b.pdf", "A.txt"]),
        "-date": (["Alpha", "zeta"], ["A.txt", "c.jpg", "b.pdf"]),
        "date": (["zeta", "Alpha"], ["b.pdf", "c.jpg", "A.txt"]),
        "-size": (["Alpha", "zeta"], ["b.pdf", "c.jpg", "A.txt"]),
        "size": (["Alpha", "zeta"], ["A.txt", "c.jpg", "b.pdf"]),
        "type": (["Alpha", "zeta"], ["c.jpg", "b.pdf", "A.txt"]),  # image, pdf, text
        "-type": (["zeta", "Alpha"], ["A.txt", "b.pdf", "c.jpg"]),
    }
    for sort, order in expected.items():
        assert contents(auth_client, sort=sort) == order, sort
    # A bad sort falls back to the saved one.
    assert contents(auth_client, sort="evil; DROP TABLE files") == expected["name"]


def test_sort_is_saved_per_folder_by_the_page(auth_client, settings):
    docs = make(auth_client, "Documents")
    upload(auth_client, "a.txt", b"x")
    upload(auth_client, "b.txt", b"xxx")
    upload_into(auth_client, docs["id"], "small.txt", b"x")
    upload_into(auth_client, docs["id"], "big.txt", b"xxxx")
    # The API doesn't save a sort.
    contents(auth_client, sort="-size")
    assert contents(auth_client) == (["Documents"], ["a.txt", "b.txt"])

    html = auth_client.get("/files", params={"folder": docs["id"], "sort": "-size"}).text
    assert html.index("big.txt") < html.index("small.txt")
    assert "Largest first" in html
    # Remembered for that folder only.
    html = auth_client.get("/files", params={"folder": docs["id"]}).text
    assert html.index("big.txt") < html.index("small.txt")
    assert contents(auth_client, docs["id"]) == ([], ["big.txt", "small.txt"])
    assert contents(auth_client) == (["Documents"], ["a.txt", "b.txt"])
    # The top level keeps its own in settings.
    auth_client.get("/files", params={"sort": "-name"})
    assert contents(auth_client) == (["Documents"], ["b.txt", "a.txt"])
    with db.connect(settings.db_path) as conn:
        assert conn.execute("SELECT value FROM settings WHERE key = 'files_sort'").fetchone()[0] == "-name"
    auth_client.get("/files", params={"sort": "nonsense"})
    assert contents(auth_client) == (["Documents"], ["b.txt", "a.txt"])


def test_sort_sheet_links_flip_the_current_sort(auth_client):
    docs = make(auth_client, "Documents")
    upload_into(auth_client, docs["id"], "a.txt")
    html = auth_client.get("/files", params={"folder": docs["id"], "sort": "-date"}).text
    sheet = html[html.index('id="sheet-sort"'):]
    assert f'href="/files?folder={docs["id"]}&amp;sort=name"' in sheet
    assert f'href="/files?folder={docs["id"]}&amp;sort=date"' in sheet  # current: flips
    assert f'href="/files?folder={docs["id"]}&amp;sort=-size"' in sheet
    assert f'href="/files?folder={docs["id"]}&amp;sort=type"' in sheet
    assert 'aria-current="true">' in sheet and "Newest first" in sheet
    assert 'href="/files?sort=-name"' in auth_client.get("/files").text


# ---- Page ------------------------------------------------------------------------------

def test_folder_page_breadcrumb_and_rows(auth_client):
    docs = make(auth_client, "Documents")
    bills = make(auth_client, "Bills", docs["id"])
    year = make(auth_client, "2026", bills["id"])
    upload_into(auth_client, year["id"], "power.pdf", b"%PDF")
    make(auth_client, "Empty", year["id"])

    html = auth_client.get("/files", params={"folder": year["id"]}).text
    assert "<title>2026 · My Vault</title>" in html
    crumb = html[html.index('class="breadcrumb"'):html.index("</nav>", html.index('class="breadcrumb"'))]
    assert re.findall(r'class="breadcrumb__link" href="([^"]+)">([^<]+)<', crumb) == [
        ("/files", "Files"), (f"/files?folder={docs['id']}", "Documents"), (f"/files?folder={bills['id']}", "Bills")]
    assert '<h1 class="breadcrumb__current" aria-current="page">2026</h1>' in crumb
    assert f'class="icon-btn topbar__back" href="/files?folder={bills["id"]}" aria-label="Back to Bills"' in html
    assert f'data-folder-id="{year["id"]}"' in html
    # Folders first, then files.
    assert html.index('data-name="Empty"') < html.index('data-name="power.pdf"')
    assert "1 folder · 1 file · 4 B" in html
    [row] = re.findall(r'<li class="row" data-name="Empty">.*?</li>', html, re.S)
    assert "Empty</span>" in row and 'data-item="/api/folders/' in row and 'data-select="folders"' in row
    assert 'id="sheet-move"' in html and 'id="modal-folder"' in html and "data-select-bar" in html
    assert_no_inline(html)

    top = auth_client.get("/files", params={"folder": docs["id"]}).text
    assert 'aria-label="Back to Files"' in top and "1 item</span>" in top
    root = auth_client.get("/files").text
    assert '<h1 class="topbar__title">Files</h1>' in root and 'data-folder-id=""' in root

    empty = auth_client.get("/files", params={"folder": make(auth_client, "Nothing")["id"]}).text
    assert "This folder is empty." in empty


def test_partial(auth_client):
    docs = make(auth_client, "Documents")
    partial = auth_client.get("/files", params={"folder": docs["id"], "partial": 1}).text
    assert "<html" not in partial and f'data-folder-id="{docs["id"]}"' in partial


@pytest.mark.parametrize("folder", ["999", "abc", "0", "-1", "1e3", "../1"])
def test_bad_folder_is_a_404_page(auth_client, folder):
    r = auth_client.get("/files", params={"folder": folder})
    assert r.status_code == 404 and "<html" in r.text


def test_folder_names_are_escaped(auth_client):
    evil = make(auth_client, '<img src=x onerror=alert(1)>"')
    make(auth_client, "<script>alert(1)</script>", evil["id"])
    for html in (auth_client.get("/files").text, auth_client.get("/files", params={"folder": evil["id"]}).text):
        assert "<img src=x" not in html and "<script>alert" not in html
        assert_no_inline(html)


# ---- Security --------------------------------------------------------------------------

@pytest.mark.parametrize("method, path", [
    ("GET", "/api/folders"), ("POST", "/api/folders"), ("PATCH", "/api/folders/1"), ("DELETE", "/api/folders/1"),
    ("GET", "/api/folders/1/summary"), ("POST", "/api/move"), ("POST", "/api/delete"), ("GET", "/files?folder=1"),
])
def test_logged_out(client, method, path):
    kwargs = {"json": {}} if method in ("POST", "PATCH") else {}
    r = client.request(method, path, follow_redirects=False, **kwargs)
    assert r.status_code == (401 if path.startswith("/api/") else 302)


@pytest.mark.parametrize("method, path, body", [
    ("POST", "/api/folders", {"name": "x", "parent_id": None}),
    ("PATCH", "/api/folders/{id}", {"name": "y"}),
    ("DELETE", "/api/folders/{id}", None),
    ("POST", "/api/move", {"files": [], "folders": ["{id}"], "to": None}),
    ("POST", "/api/delete", {"files": [], "folders": ["{id}"]}),
])
def test_foreign_origin_is_403(auth_client, method, path, body):
    folder = make(auth_client, "Keep")
    if body and "folders" in body:
        body["folders"] = [folder["id"]]
    r = auth_client.request(method, path.format(id=folder["id"]), json=body, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert contents(auth_client) == (["Keep"], [])


def test_logs_hold_ids_not_names(auth_client, caplog):
    with caplog.at_level(logging.DEBUG):
        folder = make(auth_client, "Secret Tax Papers")
        auth_client.patch(f"/api/folders/{folder['id']}", json={"name": "Hidden Plans"})
        file = upload_into(auth_client, folder["id"], "passport.pdf")
        auth_client.post("/api/move", json={"files": [file["id"]], "folders": [], "to": None})
        auth_client.post("/api/delete", json={"files": [file["id"]], "folders": []})
        auth_client.delete(f"/api/folders/{folder['id']}")
    for secret in ("Secret", "Hidden", "passport"):
        assert secret not in caplog.text
    assert f"Folder {folder['id']} created" in caplog.text
