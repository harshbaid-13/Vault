import pytest

from app.main import PLACEHOLDERS

PAGES = list(PLACEHOLDERS) + ["/settings", "/clipboard", "/notes", "/links", "/files", "/photos"]

SIDEBAR = ["/", "/files", "/photos", "/notes", "/clipboard", "/links", "/favorites", "/settings"]


@pytest.mark.parametrize("path", PAGES)
def test_pages_render_the_shell(auth_client, path):
    r = auth_client.get(path)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert 'class="sidebar"' in html
    assert 'class="tabbar"' in html
    assert 'id="sheet-more"' in html
    assert 'class="toast-region"' in html
    assert '<link rel="stylesheet" href="/static/css/app.css">' in html
    assert "<body class=\"app\" data-app data-max-upload=\"2097152\">" in html
    if path in SIDEBAR:
        assert f'href="{path}" aria-current="page"' in html
    assert html.count('aria-current="page"') <= 2  # sidebar link + tab, never two sections


@pytest.mark.parametrize("path, tab_active", [("/", True), ("/files", True), ("/clipboard", True), ("/notes", False)])
def test_more_tab_is_active_for_sections_without_a_tab(auth_client, path, tab_active):
    html = auth_client.get(path).text
    more_active = 'tabbar__tab tabbar__tab--active" type="button" data-sheet-open="sheet-more"' in html
    assert more_active is not tab_active


def test_titles(auth_client):
    assert "<title>My Vault</title>" in auth_client.get("/").text
    assert "<title>Clipboard · My Vault</title>" in auth_client.get("/clipboard").text


def test_not_found_is_a_friendly_page(auth_client):
    r = auth_client.get("/no/such/page")
    assert r.status_code == 404
    assert "This page doesn&#39;t exist" in r.text  # escaped by Jinja autoescape
    assert 'href="/">Go to Home' in r.text
    assert "detail" not in r.text


def test_api_not_found_is_json(auth_client):
    r = auth_client.get("/api/no-such-thing")
    assert r.status_code == 404
    assert r.json() == {"error": "This page doesn't exist. It may have been deleted, or the link is wrong."}


def test_static_assets_are_served(client):
    for path in ("/static/css/app.css", "/static/css/tokens.css", "/static/js/app.js", "/static/icons/upload.svg"):
        assert client.get(path).status_code == 200, path
