import logging
import re

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.security import CONTENT_SECURITY_POLICY
from tests.conftest import PASSWORD, log_in

EXPECTED = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "same-origin",
    "x-frame-options": "DENY",
    "content-security-policy": CONTENT_SECURITY_POLICY,
}


def assert_security_headers(response):
    for name, value in EXPECTED.items():
        assert response.headers.get(name) == value, name


@pytest.mark.parametrize("path", ["/", "/healthz", "/static/css/app.css", "/nope", "/api/nope", "/login"])
def test_security_headers_everywhere(auth_client, path):
    assert_security_headers(auth_client.get(path))


@pytest.mark.parametrize("path", ["/", "/api/nope", "/login"])
def test_security_headers_when_logged_out(client, path):
    assert_security_headers(client.get(path, follow_redirects=False))


def test_csp_allows_nothing_from_outside():
    assert "default-src 'self'" in CONTENT_SECURITY_POLICY
    assert "script-src 'self'" in CONTENT_SECURITY_POLICY
    assert "unsafe-inline" not in CONTENT_SECURITY_POLICY
    assert "http" not in CONTENT_SECURITY_POLICY


def test_pages_are_never_cached_but_static_files_may_be(auth_client):
    assert auth_client.get("/").headers["cache-control"] == "no-store"
    assert "no-store" not in auth_client.get("/static/css/app.css").headers.get("cache-control", "")


@pytest.mark.parametrize("path", ["/", "/favorites", "/search", "/photos", "/settings", "/clipboard", "/notes", "/links", "/links/new", "/files", "/nope"])
def test_no_inline_script_or_style(auth_client, path):
    assert_no_inline(auth_client.get(path).text)


def test_login_pages_have_no_inline_script_or_style(app, settings, client):
    assert_no_inline(client.get("/login").text)  # no password set yet
    auth.set_password(settings.db_path, PASSWORD)
    assert_no_inline(client.get("/login").text)


def assert_no_inline(html):
    assert not re.search(r"<script(?![^>]*\bsrc=)", html), "inline <script>"
    assert not re.search(r"\sstyle=", html), "style= attribute"
    assert "<style" not in html


def test_api_docs_are_not_exposed(auth_client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert auth_client.get(path).status_code == 404


def test_server_error_hides_details(app, settings, caplog):
    secret_text = "note body that must never leak"

    def boom():
        raise RuntimeError(secret_text)

    app.add_api_route("/boom", boom)
    app.add_api_route("/api/boom", boom)
    auth.set_password(settings.db_path, PASSWORD)
    with TestClient(app, raise_server_exceptions=False, headers={"Origin": "http://testserver"}) as client, \
            caplog.at_level(logging.INFO):
        log_in(client)
        page = client.get("/boom")
        api = client.get("/api/boom")

    assert page.status_code == 500
    assert "Something went wrong" in page.text
    assert secret_text not in page.text and "Traceback" not in page.text
    assert_security_headers(page)
    assert page.headers["cache-control"] == "no-store"

    assert api.status_code == 500
    assert api.json() == {"error": "The vault hit an error. Try again; if it keeps happening, check the app logs."}
    assert_security_headers(api)

    assert secret_text not in caplog.text
    assert "RuntimeError" in caplog.text


# ---- Every route, walked (S11, TECH_PLAN §5 #1) -------------------------------------------

def all_routes(app):
    """(method, path) for every route the app serves, following the included routers."""
    def walk(routes):
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                yield from walk(inner.routes)
            elif hasattr(route, "path") and getattr(route, "methods", None):
                for method in route.methods:
                    yield method, route.path
    return sorted(set(walk(app.routes)))


def fill(path):
    """A path with its parameters filled in with values that pass the route's converter."""
    return (path.replace("{file_id}", "a" * 32)
            .replace("{clip_id:int}", "1").replace("{note_id:int}", "1")
            .replace("{link_id:int}", "1").replace("{folder_id:int}", "1"))


def test_every_route_needs_login_except_the_three_public_ones(app, client):
    routes = all_routes(app)
    assert len(routes) > 40, "the walk found suspiciously few routes"
    assert ("GET", "/api/search") in routes and ("POST", "/api/move") in routes  # the walk really sees them
    checked = 0
    for method, path in routes:
        if path in ("/login", "/healthz") or path.startswith("/static"):
            continue
        checked += 1
        kwargs = {}
        if method in ("POST", "PATCH", "PUT"):
            kwargs = {"json": {}} if path.startswith("/api/") else {"data": {}}
        r = client.request(method, fill(path), follow_redirects=False, **kwargs)
        if path.startswith("/api/"):
            assert r.status_code == 401, f"{method} {path} answered {r.status_code} when logged out"
            assert r.json() == {"error": "You're logged out. Reload the page to log in again."}
        else:
            assert r.status_code in (302, 303), f"{method} {path} answered {r.status_code} when logged out"
            assert r.headers["location"].startswith("/login")
    assert checked > 40


def test_logged_out_pages_come_back_after_login(client, settings):
    """The redirect carries where you were going, and `next` can only be inside the vault."""
    r = client.get("/files?folder=3&sort=-size", follow_redirects=False)
    assert r.headers["location"] == "/login?next=%2Ffiles%3Ffolder%3D3%26sort%3D-size"
    auth.set_password(settings.db_path, PASSWORD)
    r = client.post("/login", data={"password": PASSWORD, "next": "/files?folder=3&sort=-size"}, follow_redirects=False)
    assert r.headers["location"] == "/files?folder=3&sort=-size"


# ---- Compression (S11) ---------------------------------------------------------------------

def test_pages_are_gzipped_but_file_bytes_are_not(auth_client):
    from urllib.parse import quote
    page = auth_client.get("/clipboard", headers={"Accept-Encoding": "gzip"})
    assert page.headers["content-encoding"] == "gzip"
    assert auth_client.get("/static/css/app.css", headers={"Accept-Encoding": "gzip"}).headers["content-encoding"] == "gzip"

    data = b"%PDF-1.4" + b" text that would compress well" * 200
    file = auth_client.post("/api/files", content=data, headers={
        "Content-Type": "application/octet-stream", "X-File-Name": quote("big.pdf")}).json()
    for endpoint in ("view", "download"):
        r = auth_client.get(f"/api/files/{file['id']}/{endpoint}", headers={"Accept-Encoding": "gzip"})
        assert "content-encoding" not in r.headers
        assert r.content == data
    # Range still works, and answers the exact bytes.
    r = auth_client.get(f"/api/files/{file['id']}/view", headers={"Accept-Encoding": "gzip", "Range": "bytes=0-7"})
    assert r.status_code == 206 and r.content == b"%PDF-1.4"


def test_compression_does_not_change_what_a_page_says(auth_client):
    plain = auth_client.get("/files", headers={"Accept-Encoding": "identity"})
    zipped = auth_client.get("/files", headers={"Accept-Encoding": "gzip"})
    assert plain.text == zipped.text
    assert_security_headers(zipped)
