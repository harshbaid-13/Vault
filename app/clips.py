"""Clipboard: saved text with a one-tap COPY. The reference feature (S4).

Every feature module has the same order: SQL functions, then page routes, then /api routes.
"""
import logging

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from app import db
from app.web import ApiError, render

log = logging.getLogger("vault.clips")
router = APIRouter()

MAX_TITLE = 200
MAX_CONTENT = 100_000
COLUMNS = "id, title, content, hidden, favorite, created_at, updated_at"
NOT_FOUND = "That clip no longer exists."


# ---- SQL -----------------------------------------------------------------------------

def to_clip(row) -> dict:
    clip = dict(row)
    clip["hidden"] = bool(clip["hidden"])
    clip["favorite"] = bool(clip["favorite"])
    return clip


def list_clips(conn, q: str = "") -> list[dict]:
    """Favorites first, then newest-modified. `q` matches the title, and the content of
    clips that aren't hidden (hidden content never feeds search).

    Empty clips are left out: one only exists while its editor is open, and the editor
    deletes it on leaving — a request that can land after the list has already loaded."""
    sql = f"SELECT {COLUMNS} FROM clips WHERE (title != '' OR content != '')"
    params: list[str] = []
    if q.strip():
        sql += " AND (title LIKE ? ESCAPE '\\' OR (hidden = 0 AND content LIKE ? ESCAPE '\\'))"
        params = [db.like_pattern(q.strip())] * 2
    sql += " ORDER BY favorite DESC, updated_at DESC, id DESC"
    return [to_clip(row) for row in conn.execute(sql, params)]


def get_clip(conn, clip_id: int) -> dict | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM clips WHERE id = ?", (clip_id,)).fetchone()
    return to_clip(row) if row else None


def create_clip(conn, title: str = "", content: str = "", hidden: bool = False) -> dict:
    now = db.now()
    cursor = conn.execute(
        "INSERT INTO clips (title, content, hidden, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, content, int(hidden), now, now),
    )
    return get_clip(conn, cursor.lastrowid)


def update_clip(conn, clip_id: int, fields: dict) -> dict | None:
    """`fields` comes from check_fields(), so its keys are known column names.
    Only a title or content change counts as modified: starring or hiding a clip
    doesn't move it in the list."""
    if fields:
        assignments = [f"{name} = ?" for name in fields]
        params = [int(v) if isinstance(v, bool) else v for v in fields.values()]
        if {"title", "content"} & fields.keys():
            assignments.append("updated_at = ?")
            params.append(db.now())
        conn.execute(f"UPDATE clips SET {', '.join(assignments)} WHERE id = ?", (*params, clip_id))
    return get_clip(conn, clip_id)


def delete_clip(conn, clip_id: int) -> bool:
    return conn.execute("DELETE FROM clips WHERE id = ?", (clip_id,)).rowcount > 0


def check_fields(payload: dict, allowed: set[str]) -> dict:
    """Validate a JSON body. Raises ApiError with a sentence the user can act on."""
    types = {"title": str, "content": str, "hidden": bool, "favorite": bool}
    if not payload.keys() <= allowed or any(not isinstance(v, types[k]) for k, v in payload.items()):
        raise ApiError("That request wasn't understood.", 422)
    if len(payload.get("title", "")) > MAX_TITLE:
        raise ApiError(f"The title is too long (max {MAX_TITLE} characters).", 422)
    if len(payload.get("content", "")) > MAX_CONTENT:
        raise ApiError("The text is too long (max 100,000 characters).", 422)
    return payload


# ---- Pages ---------------------------------------------------------------------------

@router.get("/clipboard")
def clipboard_page(request: Request) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        clips = list_clips(conn)
    return render(request, "clipboard.html", section="clipboard", title="Clipboard", clips=clips)


@router.post("/clipboard/new")
def new_clip(request: Request) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        clip = create_clip(conn)
    log.info("Clip %d created", clip["id"])
    return RedirectResponse(f"/clipboard/{clip['id']}", status_code=303)


@router.get("/clipboard/{clip_id:int}")
def clip_editor(request: Request, clip_id: int) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        clip = get_clip(conn, clip_id)
    if clip is None:
        raise HTTPException(404)
    return render(
        request, "editor.html", section="clipboard", title="Clipboard", no_tabbar=True,
        item=clip, noun="clip", api_url=f"/api/clips/{clip_id}", back_url="/clipboard",
        body_field="content", body_label="Text to copy", body_placeholder="Paste or type the text to copy…",
        max_body=MAX_CONTENT, can_hide=True, focus="#editor-title",
    )


# ---- API -----------------------------------------------------------------------------

@router.get("/api/clips")
def api_list(request: Request, q: str = "") -> dict:
    with db.connect(request.app.state.settings.db_path) as conn:
        return {"clips": list_clips(conn, q)}


@router.post("/api/clips", status_code=201)
def api_create(request: Request, payload: dict = Body(...)) -> dict:
    fields = check_fields(payload, {"title", "content", "hidden"})
    with db.connect(request.app.state.settings.db_path) as conn:
        clip = create_clip(conn, **fields)
    log.info("Clip %d created", clip["id"])
    return clip


@router.patch("/api/clips/{clip_id:int}")
def api_update(request: Request, clip_id: int, payload: dict = Body(...)) -> dict:
    fields = check_fields(payload, {"title", "content", "hidden", "favorite"})
    with db.connect(request.app.state.settings.db_path) as conn:
        clip = update_clip(conn, clip_id, fields)
    if clip is None:
        raise ApiError(NOT_FOUND, 404)
    return clip


@router.delete("/api/clips/{clip_id:int}", status_code=204)
def api_delete(request: Request, clip_id: int) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        deleted = delete_clip(conn, clip_id)
    if not deleted:
        raise ApiError(NOT_FOUND, 404)
    log.info("Clip %d deleted", clip_id)
    return Response(status_code=204)
