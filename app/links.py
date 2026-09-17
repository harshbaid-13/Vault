"""Links: saved URLs that open in one tap (S5). Same shape as clips.py.

Nothing here ever fetches a URL: no titles, previews or favicons from the internet.
"""
import logging
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, HTTPException, Request
from starlette.responses import Response

from app import db
from app.web import ApiError, render

log = logging.getLogger("vault.links")
router = APIRouter()

MAX_TITLE = 200
MAX_URL = 2000
MAX_DESCRIPTION = 1000
COLUMNS = "id, title, url, description, favorite, created_at, updated_at"
NOT_FOUND = "That link no longer exists."
BAD_URL = "Only web addresses starting with http:// or https:// can be saved."

SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):(.*)$", re.S)


def normalise_url(text: str, use_http: bool | None = None) -> str:
    """"example.com" → "https://example.com". Raises ApiError for anything that isn't a
    plain http(s) address, including javascript:, data: and mailto:.

    `use_http` is the link form's switch: True → http://, False → https://, whichever scheme
    was typed. None (API callers) keeps a typed scheme and adds https:// when there is none."""
    url = text.strip()
    if not url:
        raise ApiError("Enter the link's address.", 422)
    match = SCHEME.match(url)
    # "localhost:8080" and "192.168.1.1:80/admin" look like a scheme but are a host and port.
    if match and not re.match(r"^\d+(/|$)", match.group(2)):
        if match.group(1).lower() not in ("http", "https"):
            raise ApiError(BAD_URL, 422)
    else:
        url = "https://" + url
    if len(url) > MAX_URL:
        raise ApiError(f"The address is too long (max {MAX_URL} characters).", 422)
    try:
        parts = urlsplit(url)
        parts.port  # raises ValueError on a malformed port
    except ValueError:
        raise ApiError("That doesn't look like a web address.", 422) from None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname or re.search(r"[\s\x00-\x1f\x7f]", url):
        raise ApiError("That doesn't look like a web address.", 422)
    if use_http is not None:
        url = ("http" if use_http else "https") + url[len(parts.scheme):]
    return url


def host_of(url: str) -> str:
    host = urlsplit(url).hostname or ""
    return host.removeprefix("www.")


# ---- SQL -----------------------------------------------------------------------------

def to_link(row) -> dict:
    link = dict(row)
    link["favorite"] = bool(link["favorite"])
    link["host"] = host_of(link["url"])
    return link


def list_links(conn, q: str = "") -> list[dict]:
    """Favorites first, then newest saved. `q` matches title, address and description."""
    sql = f"SELECT {COLUMNS} FROM links"
    params: list[str] = []
    if q.strip():
        sql += " WHERE title LIKE ? ESCAPE '\\' OR url LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\'"
        params = [db.like_pattern(q.strip())] * 3
    sql += " ORDER BY favorite DESC, created_at DESC, id DESC"
    return [to_link(row) for row in conn.execute(sql, params)]


def get_link(conn, link_id: int) -> dict | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM links WHERE id = ?", (link_id,)).fetchone()
    return to_link(row) if row else None


def create_link(conn, url: str, title: str = "", description: str = "") -> dict:
    now = db.now()
    cursor = conn.execute(
        "INSERT INTO links (title, url, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title or host_of(url)[:MAX_TITLE], url, description, now, now),
    )
    return get_link(conn, cursor.lastrowid)


def update_link(conn, link_id: int, fields: dict) -> dict | None:
    link = get_link(conn, link_id)
    if link is None:
        return None
    fields = dict(fields)
    if "title" in fields and not fields["title"]:
        fields["title"] = host_of(fields.get("url", link["url"]))[:MAX_TITLE]
    if fields:
        assignments = [f"{name} = ?" for name in fields]
        params = [int(v) if isinstance(v, bool) else v for v in fields.values()]
        if fields.keys() - {"favorite"}:
            assignments.append("updated_at = ?")
            params.append(db.now())
        conn.execute(f"UPDATE links SET {', '.join(assignments)} WHERE id = ?", (*params, link_id))
    return get_link(conn, link_id)


def delete_link(conn, link_id: int) -> bool:
    return conn.execute("DELETE FROM links WHERE id = ?", (link_id,)).rowcount > 0


def check_fields(payload: dict, allowed: set[str]) -> dict:
    """Validate a JSON body; the URL comes back normalised and text fields trimmed."""
    types = {"url": str, "title": str, "description": str, "favorite": bool, "use_http": bool}
    if not payload.keys() <= allowed or any(not isinstance(v, types[k]) for k, v in payload.items()):
        raise ApiError("That request wasn't understood.", 422)
    fields = {k: v.strip() if isinstance(v, str) else v for k, v in payload.items()}
    use_http = fields.pop("use_http", None)
    if use_http is not None and "url" not in fields:
        raise ApiError("That request wasn't understood.", 422)
    if "url" in fields:
        fields["url"] = normalise_url(fields["url"], use_http)
    if len(fields.get("title", "")) > MAX_TITLE:
        raise ApiError(f"The title is too long (max {MAX_TITLE} characters).", 422)
    if len(fields.get("description", "")) > MAX_DESCRIPTION:
        raise ApiError(f"The description is too long (max {MAX_DESCRIPTION:,} characters).", 422)
    return fields


# ---- Pages ---------------------------------------------------------------------------

@router.get("/links")
def links_page(request: Request) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        links = list_links(conn)
    return render(request, "links.html", section="links", title="Links", links=links)


@router.get("/links/new")
def new_link_form(request: Request) -> Response:
    return render(request, "link_form.html", section="links", title="New link", no_tabbar=True, link=None)


@router.get("/links/{link_id:int}/edit")
def edit_link_form(request: Request, link_id: int) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        link = get_link(conn, link_id)
    if link is None:
        raise HTTPException(404)
    return render(request, "link_form.html", section="links", title="Edit link", no_tabbar=True, link=link)


# ---- API -----------------------------------------------------------------------------

@router.get("/api/links")
def api_list(request: Request, q: str = "") -> dict:
    with db.connect(request.app.state.settings.db_path) as conn:
        return {"links": list_links(conn, q)}


@router.post("/api/links", status_code=201)
def api_create(request: Request, payload: dict = Body(...)) -> dict:
    if "url" not in payload:
        raise ApiError("Enter the link's address.", 422)
    fields = check_fields(payload, {"url", "title", "description", "use_http"})
    with db.connect(request.app.state.settings.db_path) as conn:
        link = create_link(conn, **fields)
    log.info("Link %d created", link["id"])
    return link


@router.patch("/api/links/{link_id:int}")
def api_update(request: Request, link_id: int, payload: dict = Body(...)) -> dict:
    fields = check_fields(payload, {"url", "title", "description", "favorite", "use_http"})
    with db.connect(request.app.state.settings.db_path) as conn:
        link = update_link(conn, link_id, fields)
    if link is None:
        raise ApiError(NOT_FOUND, 404)
    return link


@router.delete("/api/links/{link_id:int}", status_code=204)
def api_delete(request: Request, link_id: int) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        deleted = delete_link(conn, link_id)
    if not deleted:
        raise ApiError(NOT_FOUND, 404)
    log.info("Link %d deleted", link_id)
    return Response(status_code=204)
