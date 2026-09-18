import re

import pytest

from tests.test_files import upload
from tests.test_folders import make
from tests.test_home import clip, link, note
from tests.test_security import assert_no_inline


@pytest.fixture
def vault(auth_client):
    """The S9 "done when": searching "bill" finds the folder, the PDF and the note."""
    make(auth_client, "Bills")
    upload(auth_client, "electricity-bill-aug.pdf", b"%PDF")
    note(auth_client, "Monthly", "Rent on the 1st.\nElectricity bill ~Rs 1,800 due on the 5th, pay online.")
    clip(auth_client, "Bill portal password", "Voltage!Spring22", hidden=True)
    clip(auth_client, "Consumer no.", "billing id 1234")
    clip(auth_client, "Secret", "the word bill is inside a hidden clip", hidden=True)
    link(auth_client, "portal.example.com/pay", "Electricity portal")
    return auth_client


def names(found):
    return {
        "folders": [f["name"] for f in found["folders"]], "files": [f["name"] for f in found["files"]],
        "notes": [n["title"] for n in found["notes"]], "clips": [c["title"] for c in found["clips"]],
        "links": [link["title"] for link in found["links"]],
    }


def test_api_finds_every_type(vault):
    found = vault.get("/api/search", params={"q": "BILL"}).json()
    assert names(found) == {
        "folders": ["Bills"], "files": ["electricity-bill-aug.pdf"], "notes": ["Monthly"],
        "clips": ["Consumer no.", "Bill portal password"], "links": [],
    }
    assert names(vault.get("/api/search", params={"q": "example.com"}).json())["links"] == ["Electricity portal"]
    assert set(found["folders"][0]) == {"id", "parent_id", "name", "sort", "created_at", "updated_at"}


def test_hidden_clips_match_by_title_only_and_stay_masked(vault):
    found = vault.get("/api/search", params={"q": "bill"}).json()
    titles = [c["title"] for c in found["clips"]]
    assert "Secret" not in titles  # its content matches, but hidden content never feeds search
    [hidden] = [c for c in found["clips"] if c["title"] == "Bill portal password"]
    assert hidden["hidden"] is True and hidden["content"] == ""
    html = vault.get("/search", params={"q": "bill"}).text
    assert "Voltage!Spring22</p>" not in html and "••••••••" in html
    # The whole text is still there for COPY, as on every list.
    assert "Voltage!Spring22</textarea>" in html


def test_type_filter(vault):
    found = vault.get("/api/search", params={"q": "bill", "type": "notes"}).json()
    assert names(found) == {"folders": [], "files": [], "notes": ["Monthly"], "clips": [], "links": []}
    found = vault.get("/api/search", params={"q": "bill", "type": "files"}).json()
    assert names(found)["folders"] == ["Bills"] and names(found)["notes"] == []


@pytest.mark.parametrize("q", ["%", "_", "100%", "a_b", "\\"])
def test_wildcards_are_literal(auth_client, q):
    note(auth_client, "plain", "nothing special here")
    note(auth_client, "discount", "100% off, a_b and a\\b")
    upload(auth_client, "report.pdf")
    upload(auth_client, "a_b.txt")
    found = auth_client.get("/api/search", params={"q": q}).json()
    everything = sum(len(v) for v in found.values())
    assert "plain" not in [n["title"] for n in found["notes"]]
    assert "report.pdf" not in [f["name"] for f in found["files"]]
    assert everything >= 1


def test_twenty_per_type(auth_client):
    for n in range(25):
        note(auth_client, f"bill {n}", "x")
    assert len(auth_client.get("/api/search", params={"q": "bill"}).json()["notes"]) == 20


def test_empty_query_finds_nothing(vault):
    found = vault.get("/api/search", params={"q": "  "}).json()
    assert all(v == [] for v in found.values())
    html = vault.get("/search").text
    assert "Search file and folder names" in html and 'class="chips"' not in html


def test_search_page_groups_snippet_and_actions(vault):
    html = vault.get("/search", params={"q": "bill"}).text
    groups = re.findall(r'id="group-(\w+)">\w+<span class="section-head__count">(\d+)', html)
    assert groups == [("files", "2"), ("notes", "1"), ("clips", "2")]
    assert "…Electricity bill ~Rs 1,800 due on the 5th, pay online." in html or "Electricity bill ~Rs 1,800" in html
    assert 'data-copy aria-label="Copy Consumer no."' in html  # COPY right in the results
    assert '<a class="row__title row__link" href="/files?folder=' in html
    assert 'value="bill"' in html and "data-live-search" in html
    assert '<a class="chip" href="/search?q=bill&type=notes">Notes</a>' in html
    assert_no_inline(html)
    partial = vault.get("/search", params={"q": "bill", "partial": 1}).text
    assert "<html" not in partial and "Monthly" in partial


def test_snippet_is_around_the_match():
    from app.home import snippet
    text = "a" * 100 + " electricity bill due " + "b" * 100
    cut = snippet(text, "BILL")
    assert cut.startswith("…") and cut.endswith("…") and "electricity bill due" in cut and len(cut) < 110
    assert snippet("no match", "zzz") == ""


def test_opened_from_a_section_starts_narrowed(vault):
    html = vault.get("/search", params={"q": "bill", "in": "notes"}).text
    assert "Monthly" in html and "electricity-bill-aug.pdf" not in html
    assert '<a class="chip" href="/search?q=bill&type=notes" aria-current="page">Notes</a>' in html
    assert 'name="type" value="notes"' in html and 'href="/notes" aria-label="Back"' in html
    wide = vault.get("/search", params={"q": "bill", "in": "notes", "type": "all"}).text
    assert "electricity-bill-aug.pdf" in wide
    assert 'href="/search?in=notes"' in vault.get("/notes").text
    assert 'href="/search" aria-label="Search"' in vault.get("/").text


def test_no_results(vault):
    html = vault.get("/search", params={"q": "zebra", "type": "notes"}).text
    assert "Nothing matches “zebra” in notes." in html and "Search everything" in html


def test_query_is_escaped(auth_client):
    html = auth_client.get("/search", params={"q": '"><script>alert(1)</script>'}).text
    assert "<script>alert(1)" not in html
    assert_no_inline(html)


def test_search_terms_are_not_logged(vault, caplog):
    import logging
    with caplog.at_level(logging.DEBUG):
        vault.get("/search", params={"q": "zebra-secret"})
        vault.get("/api/search", params={"q": "zebra-secret"})
    assert not [r for r in caplog.records if r.name.startswith("vault") and "zebra" in r.getMessage()]


@pytest.mark.parametrize("path", ["/search?q=bill", "/api/search?q=bill"])
def test_search_needs_login(client, path):
    r = client.get(path, follow_redirects=False)
    assert r.status_code == (401 if path.startswith("/api") else 302)
