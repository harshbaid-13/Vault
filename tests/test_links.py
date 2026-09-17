import logging
import re

import pytest

from app.links import normalise_url
from app.web import ApiError
from tests.test_security import assert_no_inline


def create(client, **fields):
    r = client.post("/api/links", json=fields)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.parametrize("text, url", [
    ("example.com", "https://example.com"),
    ("  example.com/a?b=1  ", "https://example.com/a?b=1"),
    ("http://192.168.1.1", "http://192.168.1.1"),
    ("192.168.1.1:8080/admin", "https://192.168.1.1:8080/admin"),
    ("localhost:8000", "https://localhost:8000"),
    ("HTTPS://Example.com/Path", "HTTPS://Example.com/Path"),
])
def test_normalise_url(text, url):
    assert normalise_url(text) == url


@pytest.mark.parametrize("text", [
    "javascript:alert(1)", "JavaScript:alert(1)", "data:text/html,<b>x</b>", "mailto:me@example.com",
    "file:///etc/passwd", "ftp://example.com", "", "   ", "https://", "http://exa mple.com", "https://a.com/\tx",
    "vbscript:msgbox", "https://example.com:port",
])
def test_bad_urls_are_rejected(text):
    with pytest.raises(ApiError) as error:
        normalise_url(text)
    assert error.value.status_code == 422


# ---- API ------------------------------------------------------------------------------

def test_create_fills_scheme_and_title(auth_client):
    link = create(auth_client, url="www.irctc.co.in/nget")
    assert set(link) == {"id", "title", "url", "host", "description", "favorite", "created_at", "updated_at"}
    assert link["url"] == "https://www.irctc.co.in/nget"
    assert link["host"] == "irctc.co.in"
    assert link["title"] == "irctc.co.in"
    assert link["description"] == ""
    link = create(auth_client, url="http://192.168.1.1", title="  Router admin ", description="the box")
    assert (link["title"], link["host"], link["description"]) == ("Router admin", "192.168.1.1", "the box")


@pytest.mark.parametrize("body, message", [
    ({"url": "javascript:alert(1)"}, "Only web addresses starting with http:// or https:// can be saved."),
    ({"url": "data:text/html,hi"}, "Only web addresses starting with http:// or https:// can be saved."),
    ({"title": "no url"}, "Enter the link's address."),
    ({"url": "  "}, "Enter the link's address."),
    ({"url": "a.com", "title": "x" * 201}, "The title is too long (max 200 characters)."),
    ({"url": "a.com", "description": "x" * 1001}, "The description is too long (max 1,000 characters)."),
    ({"url": "a.com/" + "x" * 2000}, "The address is too long (max 2000 characters)."),
    ({"url": "a.com", "favorite": True}, "That request wasn't understood."),
    ({"url": 5}, "That request wasn't understood."),
])
def test_create_validation(auth_client, body, message):
    r = auth_client.post("/api/links", json=body)
    assert r.status_code == 422 and r.json() == {"error": message}
    assert auth_client.get("/api/links").json()["links"] == []


def test_update(auth_client):
    link = create(auth_client, url="example.com", title="Example")
    url = f"/api/links/{link['id']}"
    r = auth_client.patch(url, json={"url": "portal.example.com/pay", "title": "", "description": "bills"})
    assert r.status_code == 200
    assert r.json()["url"] == "https://portal.example.com/pay"
    assert r.json()["title"] == "portal.example.com"  # emptied title → host
    assert r.json()["description"] == "bills"
    assert auth_client.patch(url, json={"favorite": True}).json()["favorite"] is True
    assert auth_client.patch(url, json={"url": "javascript:alert(1)"}).status_code == 422
    assert auth_client.get("/api/links").json()["links"][0]["url"] == "https://portal.example.com/pay"
    assert auth_client.patch("/api/links/999", json={"favorite": True}).status_code == 404


def test_list_order_and_search(auth_client):
    a = create(auth_client, url="a.example.com", title="Alpha", description="first one")
    create(auth_client, url="b.example.com", title="Beta")
    create(auth_client, url="c.example.com/100%", title="Gamma")
    assert [l["title"] for l in auth_client.get("/api/links").json()["links"]] == ["Gamma", "Beta", "Alpha"]
    auth_client.patch(f"/api/links/{a['id']}", json={"favorite": True})
    assert auth_client.get("/api/links").json()["links"][0]["title"] == "Alpha"
    def search(q):
        return [l["title"] for l in auth_client.get("/api/links", params={"q": q}).json()["links"]]
    assert search("first") == ["Alpha"]
    assert search("b.example") == ["Beta"]
    assert search("100%") == ["Gamma"]
    assert search("%") == ["Gamma"]


def test_delete(auth_client):
    link = create(auth_client, url="a.com")
    assert auth_client.delete(f"/api/links/{link['id']}").status_code == 204
    r = auth_client.delete(f"/api/links/{link['id']}")
    assert r.status_code == 404 and r.json() == {"error": "That link no longer exists."}


@pytest.mark.parametrize("method, path", [
    ("GET", "/api/links"), ("POST", "/api/links"), ("PATCH", "/api/links/1"), ("DELETE", "/api/links/1"),
])
def test_logged_out_api_is_401(client, method, path):
    assert client.request(method, path, json={} if method in ("POST", "PATCH") else None).status_code == 401


def test_logged_out_pages_go_to_login(client):
    for path in ("/links", "/links/new", "/links/1/edit"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 302 and r.headers["location"].startswith("/login")


def test_logs_hold_ids_only(auth_client, caplog):
    with caplog.at_level(logging.DEBUG):
        link = create(auth_client, url="secret-bank.example.com", title="My bank")
    assert "secret-bank" not in caplog.text and "My bank" not in caplog.text
    assert f"Link {link['id']} created" in caplog.text


# ---- Pages ----------------------------------------------------------------------------

def test_empty_list(auth_client):
    html = auth_client.get("/links").text
    assert "No links yet." in html and 'href="/links/new"' in html


def test_rows_open_in_a_new_tab_safely(auth_client):
    link = create(auth_client, url="https://www.passportindia.gov.in", title="Passport Seva", description="Renewal steps are in Notes")
    html = auth_client.get("/links").text
    [row] = re.findall(r'<li class="row">.*?</li>', html, re.S)
    assert 'href="https://www.passportindia.gov.in" target="_blank" rel="noopener noreferrer">Passport Seva</a>' in row
    assert '<span class="mono">passportindia.gov.in</span> · Just now' in row
    assert "Renewal steps are in Notes" in row
    assert 'data-copy="https://www.passportindia.gov.in"' in row
    assert f'data-edit="/links/{link["id"]}/edit"' in row
    assert 'id="sheet-link"' in html
    assert_no_inline(html)


def test_quotes_in_urls_are_escaped(auth_client):
    create(auth_client, url='example.com/?q="><script>alert(1)</script>', title="<i>t</i>")
    html = auth_client.get("/links").text
    assert "<script>alert" not in html and "<i>t</i>" not in html
    assert 'href="https://example.com/?q=&#34;&gt;&lt;script&gt;' in html


def test_forms(auth_client):
    html = auth_client.get("/links/new").text
    assert 'data-link-form="/api/links"' in html and 'data-method="POST"' in html
    assert 'inputmode="url"' in html and 'class="tabbar"' not in html
    link = create(auth_client, url="a.com", title="A & B", description="desc")
    html = auth_client.get(f"/links/{link['id']}/edit").text
    assert f'data-link-form="/api/links/{link["id"]}"' in html and 'data-method="PATCH"' in html
    assert 'value="https://a.com"' in html and 'value="A &amp; B"' in html and ">desc</textarea>" in html
    assert_no_inline(html)
    assert auth_client.get("/links/999/edit").status_code == 404


@pytest.mark.parametrize("text, use_http, url", [
    ("192.168.1.1:8080", True, "http://192.168.1.1:8080"),
    ("192.168.1.1:8080", False, "https://192.168.1.1:8080"),
    ("192.168.1.1:8080", None, "https://192.168.1.1:8080"),
    ("https://router.local", True, "http://router.local"),
    ("http://router.local", False, "https://router.local"),
    ("http://router.local", None, "http://router.local"),
])
def test_http_switch(text, use_http, url):
    assert normalise_url(text, use_http) == url


def test_http_switch_over_the_api(auth_client):
    link = create(auth_client, url="localhost:8000", use_http=True)
    assert link["url"] == "http://localhost:8000" and "use_http" not in link
    assert create(auth_client, url="localhost:8000")["url"] == "https://localhost:8000"  # https stays the default
    r = auth_client.patch(f"/api/links/{link['id']}", json={"url": link["url"], "use_http": False})
    assert r.json()["url"] == "https://localhost:8000"
    assert auth_client.patch(f"/api/links/{link['id']}", json={"use_http": True}).status_code == 422  # needs url
    assert auth_client.post("/api/links", json={"url": "a.com", "use_http": "yes"}).status_code == 422
    assert auth_client.post("/api/links", json={"url": "javascript:alert(1)", "use_http": True}).status_code == 422


def test_form_http_switch_reflects_the_link(auth_client):
    assert 'name="use_http">' in auth_client.get("/links/new").text
    link = create(auth_client, url="192.168.1.1", use_http=True)
    assert 'name="use_http" checked>' in auth_client.get(f"/links/{link['id']}/edit").text
