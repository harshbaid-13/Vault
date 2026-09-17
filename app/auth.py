"""Password, sessions, /login, /logout and /api/password.

The password is stored only as an Argon2id hash in the settings table. `session_version`
is copied into the session cookie at login; bumping it (any password change) logs out
every session that still carries the old number.
"""
import logging
from pathlib import Path
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Body, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

from app import db
from app.web import render

log = logging.getLogger("vault.auth")

MIN_PASSWORD_LENGTH = 4
SET_PASSWORD_COMMAND = "docker compose run --rm vault python -m app.cli set-password"
WRONG_PASSWORD = "Wrong password."

hasher = PasswordHasher()
router = APIRouter()


# ---- Password and session version ----------------------------------------------------

def _get_setting(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def password_state(db_path: Path) -> tuple[str | None, int]:
    """(password hash or None, current session version)."""
    with db.connect(db_path) as conn:
        return _get_setting(conn, "password_hash"), int(_get_setting(conn, "session_version") or 0)


def set_password(db_path: Path, password: str) -> int:
    """Store a new hash and bump the session version. Returns the new version."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"The password needs at least {MIN_PASSWORD_LENGTH} characters.")
    password_hash = hasher.hash(password)
    with db.connect(db_path) as conn:
        version = int(_get_setting(conn, "session_version") or 0) + 1
        conn.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            [("password_hash", password_hash), ("session_version", str(version))],
        )
    log.info("Password changed; older sessions are logged out")
    return version


def check_password(password_hash: str | None, password: str) -> bool:
    if not password_hash or not password:
        return False
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def is_logged_in(session: dict, db_path: Path) -> bool:
    password_hash, version = password_state(db_path)
    return bool(password_hash) and session.get("v") == version


def safe_next(target: str | None) -> str:
    """Only a path on this site: starts with one /, no backslash, no scheme or host."""
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/"
    if any(ord(ch) < 32 for ch in target):
        return "/"
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return "/"
    return target


def wait_text(seconds: int) -> str:
    if seconds > 90:
        minutes = -(-seconds // 60)
        return f"Too many attempts. Try again in {minutes} minutes."
    return f"Too many attempts. Try again in {seconds} second{'' if seconds == 1 else 's'}."


# ---- Pages ---------------------------------------------------------------------------

def login_page(request: Request, next_path: str, error: str = "", wait: int = 0, status_code: int = 200) -> Response:
    password_hash, _ = password_state(request.app.state.settings.db_path)
    response = render(
        request, "login.html", status_code=status_code,
        has_password=bool(password_hash), command=SET_PASSWORD_COMMAND,
        next=next_path, error=error, wait=wait,
    )
    if wait:
        response.headers["Retry-After"] = str(wait)
    return response


@router.get("/login")
def login_form(request: Request, next: str = "/") -> Response:
    if is_logged_in(request.session, request.app.state.settings.db_path):
        return RedirectResponse(safe_next(next), status_code=303)
    return login_page(request, safe_next(next))


@router.post("/login")
def login_post(request: Request, password: str = Form(""), next: str = Form("/")) -> Response:
    settings = request.app.state.settings
    limiter = request.app.state.limiter
    next_path = safe_next(next)

    password_hash, version = password_state(settings.db_path)
    if not password_hash:
        return login_page(request, next_path)

    wait = limiter.wait()
    if wait:
        return login_page(request, next_path, error=wait_text(wait), wait=wait, status_code=429)

    if not check_password(password_hash, password):
        wait = limiter.fail()
        log.info("Failed login")
        if wait:
            return login_page(request, next_path, error=wait_text(wait), wait=wait, status_code=429)
        return login_page(request, next_path, error=WRONG_PASSWORD)

    limiter.reset()
    request.session.clear()
    request.session["v"] = version
    log.info("Logged in")
    return RedirectResponse(next_path, status_code=303)


@router.post("/logout")
def logout(request: Request) -> Response:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---- API -----------------------------------------------------------------------------

def _error(message: str, status_code: int, **headers: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code, headers=headers or None)


@router.post("/api/password")
def change_password(request: Request, payload: dict = Body(...)) -> Response:
    settings = request.app.state.settings
    limiter = request.app.state.limiter

    wait = limiter.wait()
    if wait:
        return _error(wait_text(wait), 429, **{"Retry-After": str(wait)})

    current = payload.get("current")
    new = payload.get("new")
    if not isinstance(current, str) or not current:
        return _error("Enter your current password.", 422)

    password_hash, _ = password_state(settings.db_path)
    if not check_password(password_hash, current):
        wait = limiter.fail()
        log.info("Wrong current password on password change")
        if wait:
            return _error(wait_text(wait), 429, **{"Retry-After": str(wait)})
        return _error("Current password is wrong.", 400)

    if not isinstance(new, str) or len(new) < MIN_PASSWORD_LENGTH:
        return _error(f"The new password needs at least {MIN_PASSWORD_LENGTH} characters.", 422)

    limiter.reset()
    request.session["v"] = set_password(settings.db_path, new)
    return Response(status_code=204)
