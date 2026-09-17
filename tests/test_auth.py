import logging
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app import auth
from app.security import LoginLimiter
from tests.conftest import PASSWORD, TEST_SECRET, log_in, make_client

ROOT = Path(__file__).resolve().parent.parent
NEW_PASSWORD = "a brand new passphrase"


@pytest.fixture
def with_password(app, settings):
    auth.set_password(settings.db_path, PASSWORD)


def stored(settings, key):
    with sqlite3.connect(settings.db_path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


# ---- Password storage -------------------------------------------------------------------

def test_password_is_stored_as_argon2id_only(app, settings, caplog):
    with caplog.at_level(logging.DEBUG):
        auth.set_password(settings.db_path, PASSWORD)
    assert stored(settings, "password_hash").startswith("$argon2id$")
    assert PASSWORD not in settings.db_path.read_bytes().decode("latin-1")
    assert PASSWORD not in caplog.text


def test_short_password_is_refused(app, settings):
    with pytest.raises(ValueError):
        auth.set_password(settings.db_path, "abc")
    assert stored(settings, "password_hash") is None


def test_four_character_password_is_enough(app, client, settings):
    auth.set_password(settings.db_path, "abcd")
    log_in(client, "abcd")


def test_cli_sets_the_password(tmp_path, monkeypatch, capsys):
    from app import cli

    data = tmp_path / "data"
    monkeypatch.setenv("SESSION_SECRET", TEST_SECRET)
    monkeypatch.setenv("VAULT_DATA_DIR", str(data))
    answers = iter([PASSWORD, PASSWORD])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(answers))
    assert cli.main(["set-password"]) == 0
    assert PASSWORD not in capsys.readouterr().out
    password_hash, version = auth.password_state(data / "vault.db")
    assert auth.check_password(password_hash, PASSWORD) and version == 1


@pytest.mark.parametrize("answers", [["abc", "abc"], [PASSWORD, PASSWORD + "x"]])
def test_cli_refuses_short_or_mismatched(tmp_path, monkeypatch, capsys, answers):
    from app import cli

    monkeypatch.setenv("SESSION_SECRET", TEST_SECRET)
    monkeypatch.setenv("VAULT_DATA_DIR", str(tmp_path / "data"))
    it = iter(answers)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: next(it))
    assert cli.main(["set-password"]) == 1
    assert "Not changed" in capsys.readouterr().err
    assert auth.password_state(tmp_path / "data" / "vault.db") == (None, 0)


def test_cli_runs_as_a_module_without_a_terminal(tmp_path):
    # No tty: getpass reads stdin. Proves `python -m app.cli` is wired up.
    env = {"PATH": "/usr/bin:/bin", "SESSION_SECRET": TEST_SECRET, "VAULT_DATA_DIR": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "set-password"], cwd=ROOT, env=env,
        input=f"{PASSWORD}\n{PASSWORD}\n", capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr


# ---- Login and logout -------------------------------------------------------------------

def test_login_page_shows_the_command_until_a_password_is_set(client, settings):
    html = client.get("/login").text
    assert auth.SET_PASSWORD_COMMAND in html
    assert 'name="password"' not in html
    r = client.post("/login", data={"password": "anything at all"}, follow_redirects=False)
    assert r.status_code == 200 and auth.SET_PASSWORD_COMMAND in r.text
    assert client.get("/", follow_redirects=False).status_code == 302


def test_correct_password_logs_in(client, with_password):
    r = client.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert client.get("/", follow_redirects=False).status_code == 200


def test_wrong_password_fails_with_the_same_message(client, with_password):
    for password in ("wrong password!", "", PASSWORD.upper()):
        r = client.post("/login", data={"password": password}, follow_redirects=False)
        assert r.status_code == 200
        assert "Wrong password." in r.text
    assert client.get("/", follow_redirects=False).status_code == 302


def test_session_cookie_flags(client, with_password):
    r = client.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    cookie = r.headers["set-cookie"].lower()
    assert "vault_session=" in cookie
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert f"max-age={30 * 24 * 60 * 60}" in cookie
    assert "secure" not in cookie


def test_cookie_is_secure_when_set(tmp_path):
    from app.config import Settings
    from app.main import create_app

    settings = Settings(session_secret=TEST_SECRET, data_dir=tmp_path / "data", cookie_secure=True)
    app = create_app(settings)
    auth.set_password(settings.db_path, PASSWORD)
    with make_client(app) as c:
        r = c.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    assert "; secure" in r.headers["set-cookie"].lower()


def test_logged_in_visit_to_login_goes_home(auth_client):
    r = auth_client.get("/login", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"


def test_logout_clears_access(auth_client):
    r = auth_client.post("/logout", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert auth_client.get("/", follow_redirects=False).status_code == 302
    assert auth_client.get("/api/anything").status_code == 401


def test_old_cookie_stops_working_after_logout_elsewhere_by_password_change(app, settings, auth_client):
    stolen = dict(auth_client.cookies)
    auth.set_password(settings.db_path, NEW_PASSWORD)  # e.g. the CLI
    with make_client(app) as other:
        other.cookies.update(stolen)
        assert other.get("/", follow_redirects=False).status_code == 302


def test_forged_cookie_is_ignored(client, with_password):
    client.cookies.set("vault_session", "eyJ2IjogMX0=.forged.signature")
    assert client.get("/", follow_redirects=False).status_code == 302


# ---- The gate ---------------------------------------------------------------------------

def all_routes(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):  # include_router() nests the router's routes
            yield from all_routes(route.original_router.routes)


def test_every_non_public_route_needs_login(app, client, with_password):
    checked = 0
    for route in all_routes(app.routes):
        path = route.path.replace("{", "").replace("}", "")
        if path in ("/login", "/healthz"):
            continue
        for method in route.methods - {"HEAD"}:
            r = client.request(method, path, json={} if method != "GET" else None, follow_redirects=False)
            if path.startswith("/api/"):
                assert r.status_code == 401, (method, path)
                assert r.json() == {"error": "You're logged out. Reload the page to log in again."}
            else:
                assert r.status_code in (302, 303), (method, path)
                assert r.headers["location"].startswith("/login"), (method, path)
            checked += 1
    assert {"/logout", "/api/password", "/settings"} <= {r.path for r in all_routes(app.routes)}
    assert checked >= 11


def test_redirect_remembers_the_page(client, with_password):
    r = client.get("/notes?q=tax", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login?next=%2Fnotes%3Fq%3Dtax"
    r = client.post("/login", data={"password": PASSWORD, "next": "/notes?q=tax"}, follow_redirects=False)
    assert r.headers["location"] == "/notes?q=tax"


def test_unknown_paths_do_not_reveal_anything_when_logged_out(client, with_password):
    assert client.get("/no/such/page", follow_redirects=False).status_code == 302
    assert client.get("/api/no-such-thing").status_code == 401


def test_public_paths_stay_public(client, with_password):
    assert client.get("/healthz").status_code == 200
    assert client.get("/static/css/app.css").status_code == 200
    assert client.get("/login").status_code == 200


@pytest.mark.parametrize("target", [
    "https://evil.example", "//evil.example", "/\\evil.example", "\\\\evil.example",
    "javascript:alert(1)", "http:/evil.example", "evil.example", "/\tevil", "",
])
def test_next_cannot_leave_the_site(client, with_password, target):
    r = client.post("/login", data={"password": PASSWORD, "next": target}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_next_is_ignored_on_the_login_form_too(client, with_password):
    html = client.get("/login?next=https://evil.example").text
    assert 'name="next" value="/"' in html


# ---- Lockout ----------------------------------------------------------------------------

def test_sixth_attempt_is_blocked_even_with_the_right_password(client, with_password):
    for _ in range(4):
        assert client.post("/login", data={"password": "nope nope nope"}).status_code == 200
    fifth = client.post("/login", data={"password": "nope nope nope"})
    assert fifth.status_code == 429
    assert "Too many attempts. Try again in 60 seconds." in fifth.text
    assert fifth.headers["retry-after"] == "60"
    assert 'data-retry-after="60"' in fifth.text and "disabled" in fifth.text

    sixth = client.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    assert sixth.status_code == 429
    assert client.get("/", follow_redirects=False).status_code == 302


def test_lock_doubles_up_to_fifteen_minutes_and_resets_on_success():
    now = [1000.0]
    limiter = LoginLimiter(clock=lambda: now[0])
    assert [limiter.fail() for _ in range(4)] == [0, 0, 0, 0]
    locks = []
    for _ in range(6):
        locks.append(limiter.fail())
        assert limiter.wait() == locks[-1]
        now[0] += locks[-1]
        assert limiter.wait() == 0
    assert locks == [60, 120, 240, 480, 900, 900]
    limiter.reset()
    assert [limiter.fail() for _ in range(4)] == [0, 0, 0, 0]


def test_lock_ends_and_the_right_password_works(app, client, with_password):
    now = [0.0]
    app.state.limiter = LoginLimiter(clock=lambda: now[0])
    for _ in range(5):
        client.post("/login", data={"password": "nope nope nope"})
    now[0] += 61
    log_in(client)


def test_failed_logins_are_logged_without_the_password(client, with_password, caplog):
    with caplog.at_level(logging.INFO):
        client.post("/login", data={"password": "my-secret-guess"})
        client.post("/login", data={"password": PASSWORD})
    assert "Failed login" in caplog.text
    assert "my-secret-guess" not in caplog.text and PASSWORD not in caplog.text


# ---- Origin check -----------------------------------------------------------------------

def test_post_with_a_foreign_origin_is_rejected(client, with_password):
    r = client.post("/login", data={"password": PASSWORD}, headers={"Origin": "https://evil.example"}, follow_redirects=False)
    assert r.status_code == 403
    assert "set-cookie" not in r.headers


def test_foreign_origin_cannot_log_you_out(auth_client):
    r = auth_client.post("/logout", headers={"Origin": "https://evil.example"}, follow_redirects=False)
    assert r.status_code == 403
    assert auth_client.get("/", follow_redirects=False).status_code == 200


def test_api_post_with_a_foreign_origin_is_json_403(auth_client):
    r = auth_client.post("/api/password", json={}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert "error" in r.json()


def test_post_with_no_origin_and_no_referer_is_rejected(app, with_password):
    with make_client(app) as c:
        del c.headers["origin"]
        assert c.post("/login", data={"password": PASSWORD}).status_code == 403


def test_referer_is_used_when_origin_is_missing(app, with_password):
    with make_client(app) as c:
        del c.headers["origin"]
        r = c.post("/login", data={"password": PASSWORD}, headers={"Referer": "http://testserver/login?next=/"},
                   follow_redirects=False)
        assert r.status_code == 303
        r = c.post("/logout", headers={"Referer": "http://evil.example/testserver"}, follow_redirects=False)
        assert r.status_code == 403


def test_allowed_origins_are_accepted(tmp_path):
    from app.config import Settings
    from app.main import create_app

    origin = "https://office-vault.tail1234.ts.net"
    settings = Settings(session_secret=TEST_SECRET, data_dir=tmp_path / "data", allowed_origins=(origin,))
    app = create_app(settings)
    auth.set_password(settings.db_path, PASSWORD)
    with make_client(app) as c:
        r = c.post("/login", data={"password": PASSWORD}, headers={"Origin": origin}, follow_redirects=False)
        assert r.status_code == 303
        r = c.post("/logout", headers={"Origin": "https://other.tail1234.ts.net"}, follow_redirects=False)
        assert r.status_code == 403


def test_api_writes_must_be_json(auth_client):
    r = auth_client.post("/api/password", data={"current": PASSWORD, "new": NEW_PASSWORD})
    assert r.status_code == 415
    assert r.json() == {"error": "That request wasn't understood."}


def test_safe_methods_skip_the_origin_check(auth_client):
    assert auth_client.get("/", headers={"Origin": "https://evil.example"}).status_code == 200


# ---- Change password (TECH_PLAN §5 #23) -------------------------------------------------

def test_change_password_needs_the_right_current_password(app, settings, auth_client):
    r = auth_client.post("/api/password", json={"current": "not my password", "new": NEW_PASSWORD})
    assert r.status_code == 400
    assert r.json() == {"error": "Current password is wrong."}
    with make_client(app) as other:
        log_in(other, PASSWORD)  # old password still works


def test_change_password_needs_a_current_password(settings, auth_client):
    before = stored(settings, "password_hash")
    r = auth_client.post("/api/password", json={"new": NEW_PASSWORD})
    assert r.status_code == 422
    assert r.json() == {"error": "Enter your current password."}
    assert stored(settings, "password_hash") == before


def test_change_password_needs_a_long_new_password(settings, auth_client):
    before = stored(settings, "password_hash")
    r = auth_client.post("/api/password", json={"current": PASSWORD, "new": "abc"})
    assert r.status_code == 422
    assert "4 characters" in r.json()["error"]
    assert stored(settings, "password_hash") == before


def test_change_password_bad_json_is_a_plain_error(auth_client):
    r = auth_client.post("/api/password", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json() == {"error": "That request wasn't understood."}


def test_wrong_current_password_counts_toward_the_lockout(auth_client):
    for _ in range(4):
        assert auth_client.post("/api/password", json={"current": "guess guess", "new": NEW_PASSWORD}).status_code == 400
    r = auth_client.post("/api/password", json={"current": "guess guess", "new": NEW_PASSWORD})
    assert r.status_code == 429
    r = auth_client.post("/api/password", json={"current": PASSWORD, "new": NEW_PASSWORD})
    assert r.status_code == 429
    assert r.headers["retry-after"]


def test_change_password_keeps_this_session_and_logs_out_the_others(app, auth_client, caplog):
    with make_client(app) as other:
        log_in(other)
        with caplog.at_level(logging.DEBUG):
            r = auth_client.post("/api/password", json={"current": PASSWORD, "new": NEW_PASSWORD})
        assert r.status_code == 204
        assert auth_client.get("/", follow_redirects=False).status_code == 200
        assert other.get("/", follow_redirects=False).status_code == 302
    assert NEW_PASSWORD not in caplog.text and PASSWORD not in caplog.text

    with make_client(app) as fresh:
        assert fresh.post("/login", data={"password": PASSWORD}).status_code == 200  # old fails
        log_in(fresh, NEW_PASSWORD)


# ---- Pages ------------------------------------------------------------------------------

def test_logout_is_in_the_sidebar_the_more_sheet_and_settings(auth_client):
    for path in ("/", "/settings"):
        html = auth_client.get(path).text
        assert html.count('action="/logout" method="post"') == (3 if path == "/settings" else 2)
    assert 'data-modal-open="modal-password"' in auth_client.get("/settings").text


def test_login_form_matches_the_mockup(client, with_password):
    html = client.get("/login").text
    assert 'class="login__form" action="/login" method="post"' in html
    assert 'autocomplete="current-password"' in html
    assert "Wrong password." not in html
