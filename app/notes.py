"""Notes: plain-text notes with autosave (S5). Same shape as clips.py."""
import logging

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from app import db
from app.web import ApiError, render

log = logging.getLogger("vault.notes")
router = APIRouter()

MAX_TITLE = 200
MAX_BODY = 1_000_000
COLUMNS = "id, title, body, favorite, created_at, updated_at"
NOT_FOUND = "That note no longer exists."


# ---- SQL -----------------------------------------------------------------------------

def to_note(row) -> dict:
    note = dict(row)
    note["favorite"] = bool(note["favorite"])
    return note


def list_notes(conn, q: str = "") -> list[dict]:
    """Favorites first, then newest-modified. Empty notes are left out, as with clips."""
    sql = f"SELECT {COLUMNS} FROM notes WHERE (title != '' OR body != '')"
    params: list[str] = []
    if q.strip():
        sql += " AND (title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\')"
        params = [db.like_pattern(q.strip())] * 2
    sql += " ORDER BY favorite DESC, updated_at DESC, id DESC"
    return [to_note(row) for row in conn.execute(sql, params)]


def get_note(conn, note_id: int) -> dict | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM notes WHERE id = ?", (note_id,)).fetchone()
    return to_note(row) if row else None


def create_note(conn, title: str = "", body: str = "") -> dict:
    now = db.now()
    cursor = conn.execute(
        "INSERT INTO notes (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title, body, now, now),
    )
    return get_note(conn, cursor.lastrowid)


def update_note(conn, note_id: int, fields: dict) -> dict | None:
    """`fields` comes from check_fields(). Starring isn't an edit, so it keeps updated_at."""
    if fields:
        assignments = [f"{name} = ?" for name in fields]
        params = [int(v) if isinstance(v, bool) else v for v in fields.values()]
        if {"title", "body"} & fields.keys():
            assignments.append("updated_at = ?")
            params.append(db.now())
        conn.execute(f"UPDATE notes SET {', '.join(assignments)} WHERE id = ?", (*params, note_id))
    return get_note(conn, note_id)


def delete_note(conn, note_id: int) -> bool:
    return conn.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount > 0


def check_fields(payload: dict, allowed: set[str]) -> dict:
    types = {"title": str, "body": str, "favorite": bool}
    if not payload.keys() <= allowed or any(not isinstance(v, types[k]) for k, v in payload.items()):
        raise ApiError("That request wasn't understood.", 422)
    if len(payload.get("title", "")) > MAX_TITLE:
        raise ApiError(f"The title is too long (max {MAX_TITLE} characters).", 422)
    if len(payload.get("body", "")) > MAX_BODY:
        raise ApiError("The note is too long (max 1,000,000 characters).", 422)
    return payload


# ---- Pages ---------------------------------------------------------------------------

@router.get("/notes")
def notes_page(request: Request) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        notes = list_notes(conn)
    return render(request, "notes.html", section="notes", title="Notes", notes=notes)


@router.post("/notes/new")
def new_note(request: Request) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        note = create_note(conn)
    log.info("Note %d created", note["id"])
    return RedirectResponse(f"/notes/{note['id']}", status_code=303)


@router.get("/notes/{note_id:int}")
def note_editor(request: Request, note_id: int) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        note = get_note(conn, note_id)
    if note is None:
        raise HTTPException(404)
    return render(
        request, "editor.html", section="notes", title="Notes", no_tabbar=True,
        item=note, noun="note", api_url=f"/api/notes/{note_id}", back_url="/notes",
        body_field="body", body_label="Note", body_placeholder="Start writing…",
        max_body=MAX_BODY, can_hide=False, focus="#editor-body",
    )


# ---- API -----------------------------------------------------------------------------

@router.get("/api/notes")
def api_list(request: Request, q: str = "") -> dict:
    with db.connect(request.app.state.settings.db_path) as conn:
        return {"notes": list_notes(conn, q)}


@router.post("/api/notes", status_code=201)
def api_create(request: Request, payload: dict = Body(...)) -> dict:
    fields = check_fields(payload, {"title", "body"})
    with db.connect(request.app.state.settings.db_path) as conn:
        note = create_note(conn, **fields)
    log.info("Note %d created", note["id"])
    return note


@router.patch("/api/notes/{note_id:int}")
def api_update(request: Request, note_id: int, payload: dict = Body(...)) -> dict:
    fields = check_fields(payload, {"title", "body", "favorite"})
    with db.connect(request.app.state.settings.db_path) as conn:
        note = update_note(conn, note_id, fields)
    if note is None:
        raise ApiError(NOT_FOUND, 404)
    return note


@router.delete("/api/notes/{note_id:int}", status_code=204)
def api_delete(request: Request, note_id: int) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        deleted = delete_note(conn, note_id)
    if not deleted:
        raise ApiError(NOT_FOUND, 404)
    log.info("Note %d deleted", note_id)
    return Response(status_code=204)
