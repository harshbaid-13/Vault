import logging
import re

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import PLACEHOLDERS
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


@pytest.mark.parametrize("path", list(PLACEHOLDERS) + ["/settings", "/clipboard", "/notes", "/links", "/links/new", "/files", "/nope"])
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
