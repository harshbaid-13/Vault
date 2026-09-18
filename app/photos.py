"""Photos: every image and video across all folders, newest first, and the full-screen viewer (S8).

A view over the files table, not a separate store. Same shape as the other features: SQL, pages.
"""
import re

from fastapi import APIRouter, Request
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app import db, files, storage
from app.web import render

router = APIRouter()

PAGE = 60
NEIGHBOURS = 10  # slides each side of the one opened; the viewer reloads around the edge ones
PHOTO_KINDS = "kind IN ('image', 'video')"
CURSOR = re.compile(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ),([0-9a-f]{32})")


# ---- SQL -----------------------------------------------------------------------------

def list_photos(conn, before: tuple[str, str] | None = None, limit: int = PAGE) -> list[dict]:
    """Newest first. `before` is the (created_at, id) of the last tile already shown."""
    sql = f"SELECT {files.COLUMNS} FROM files WHERE {PHOTO_KINDS}"
    params: list = []
    if before:
        sql += " AND (created_at, id) < (?, ?)"
        params = list(before)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    return [files.to_file(row) for row in conn.execute(sql, (*params, limit))]


def list_newer(conn, file: dict, limit: int) -> list[dict]:
    """The photos just newer than `file`, nearest first."""
    rows = conn.execute(
        f"SELECT {files.COLUMNS} FROM files WHERE {PHOTO_KINDS} AND (created_at, id) > (?, ?)"
        " ORDER BY created_at, id LIMIT ?",
        (file["created_at"], file["id"], limit),
    )
    return [files.to_file(row) for row in rows]


# ---- Pages ---------------------------------------------------------------------------

@router.get("/photos")
def photos_page(request: Request, before: str | None = None) -> Response:
    """60 tiles a page under month headings. ?before= (with ?partial=1) is the next page."""
    cursor = None
    if before:
        match = CURSOR.fullmatch(before)
        if not match:
            raise HTTPException(404)
        cursor = (match[1], match[2])
    with db.connect(request.app.state.settings.db_path) as conn:
        photos = list_photos(conn, cursor, PAGE + 1)
    more = len(photos) > PAGE
    photos = photos[:PAGE]
    next_page = f"{photos[-1]['created_at']},{photos[-1]['id']}" if more else None
    return render(request, "photos.html", section="photos", title="Photos", photos=photos,
                  next_page=next_page, first_page=cursor is None)


@router.get("/photos/{file_id}")
def viewer_page(request: Request, file_id: str) -> Response:
    """One photo or video full screen, with its neighbours as slides to swipe to."""
    file = None
    with db.connect(request.app.state.settings.db_path) as conn:
        if files.valid_id(file_id):
            file = files.get_file(conn, file_id)
        if file is None or file["kind"] not in ("image", "video"):
            raise HTTPException(404)
        newer = list_newer(conn, file, NEIGHBOURS + 1)
        older = list_photos(conn, (file["created_at"], file["id"]), NEIGHBOURS + 1)
    slides = list(reversed(newer[:NEIGHBOURS])) + [file] + older[:NEIGHBOURS]
    for slide in slides:
        slide["inline"] = storage.inline_type(slide["name"]) is not None  # HEIC, MKV: no preview
    return render(request, "viewer.html", title=file["name"], slides=slides, current=file,
                  more_newer=len(newer) > NEIGHBOURS, more_older=len(older) > NEIGHBOURS)
