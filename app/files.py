"""Files: upload, list, download/view, rename, favorite, delete (S6), and the Files page with
its folders (S7). Folder SQL and the move/delete-many routes are in folders.py.

Same shape as clips.py. The upload and file-serving routes are async so a 2 GB stream never
holds a thread (TECH_PLAN §7); everything else is plain def.
"""
import logging
import sqlite3
from urllib.parse import unquote, urlencode

from fastapi import APIRouter, Body, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app import db, folders, storage
from app.web import ApiError, render

log = logging.getLogger("vault.files")
router = APIRouter()

COLUMNS = "id, folder_id, name, size, mime, kind, favorite, created_at, updated_at"
NOT_FOUND = "That file no longer exists."

# File responses carry their own policy; the page-wide headers fill in the rest.
FILE_CSP = "sandbox; default-src 'none'"
# Chrome won't render a PDF under a sandbox CSP, and S8 embeds it in a same-origin iframe
# (TECH_PLAN §8 gotcha 7). A PDF is not HTML, so it gets frame-ancestors only.
PDF_CSP = "default-src 'none'; frame-ancestors 'self'"


# ---- SQL -----------------------------------------------------------------------------

def to_file(row) -> dict:
    file = dict(row)
    file["favorite"] = bool(file["favorite"])
    return file


def list_files(conn, folder_id: int | None, sort: str) -> list[dict]:
    """The files directly in one folder. rowid breaks ties in upload order (ids are random)."""
    rows = conn.execute(
        f"SELECT {COLUMNS} FROM files WHERE folder_id IS ? ORDER BY {folders.order_by(folders.FILE_ORDER, sort)}",
        (folder_id,),
    )
    return [to_file(row) for row in rows]


def get_file(conn, file_id: str) -> dict | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM files WHERE id = ?", (file_id,)).fetchone()
    return to_file(row) if row else None


def insert_file(conn, file_id: str, name: str, size: int, sha256: str, folder_id: int | None = None) -> dict:
    kind, mime = storage.kind_and_mime(name)
    now = db.now()
    try:
        conn.execute(
            "INSERT INTO files (id, folder_id, name, size, sha256, mime, kind, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_id, folder_id, name, size, sha256, mime, kind, now, now),
        )
    except sqlite3.IntegrityError:
        # The folder was deleted while the file was uploading.
        raise ApiError(folders.NOT_FOUND, 404) from None
    return get_file(conn, file_id)


def update_file(conn, file_id: str, fields: dict) -> dict | None:
    """A rename also re-reads the type from the new extension. Starring or moving isn't an edit."""
    fields = dict(fields)
    if "folder_id" in fields:
        folders.check_parent(conn, fields["folder_id"])
    if "name" in fields:
        fields["kind"], fields["mime"] = storage.kind_and_mime(fields["name"])
    if fields:
        assignments = [f"{name} = ?" for name in fields]
        params = [int(v) if isinstance(v, bool) else v for v in fields.values()]
        if "name" in fields:
            assignments.append("updated_at = ?")
            params.append(db.now())
        conn.execute(f"UPDATE files SET {', '.join(assignments)} WHERE id = ?", (*params, file_id))
    return get_file(conn, file_id)


def delete_file_row(conn, file_id: str) -> bool:
    return conn.execute("DELETE FROM files WHERE id = ?", (file_id,)).rowcount > 0


def check_fields(payload: dict, allowed: set[str]) -> dict:
    types = {"name": str, "favorite": bool}
    if not payload.keys() <= allowed or any(not isinstance(v, types[k]) for k, v in payload.items() if k in types):
        raise ApiError("That request wasn't understood.", 422)
    if "folder_id" in payload and not (payload["folder_id"] is None or folders.is_id(payload["folder_id"])):
        raise ApiError("That request wasn't understood.", 422)
    fields = dict(payload)
    if "name" in fields:
        if not fields["name"].strip(" ."):
            raise ApiError("Enter a name.", 422)
        fields["name"] = storage.clean_name(fields["name"])
    return fields


def valid_id(file_id: str) -> bool:
    return bool(storage.ID_PATTERN.fullmatch(file_id))


# ---- Pages ---------------------------------------------------------------------------

def sort_options(folder_id: int | None, current: str) -> list[dict]:
    """The sort sheet: each choice links to its natural direction, or flips when it's current."""
    options = []
    for key, label, first in folders.SORT_CHOICES:
        active = current.lstrip("-") == key
        sort = ("" if current.startswith("-") else "-") + key if active else first
        query = {"folder": folder_id, "sort": sort} if folder_id else {"sort": sort}
        options.append({"label": label, "href": f"/files?{urlencode(query)}", "active": active,
                        "direction": folders.SORTS[current].removeprefix(f"{label} ") if active else ""})
    return options


@router.get("/files")
def files_page(request: Request, folder: str | None = None, sort: str | None = None) -> Response:
    """One folder: sub-folders first, then files. A valid `sort` is saved to the folder."""
    try:
        folder_id = folders.parse_folder_param(folder)
    except ValueError:
        raise HTTPException(404) from None
    with db.connect(request.app.state.settings.db_path) as conn:
        current = folders.get_folder(conn, folder_id) if folder_id else None
        if folder_id and current is None:
            raise HTTPException(404)
        if sort in folders.SORTS:
            folders.save_sort(conn, folder_id, sort)
        else:
            sort = folders.get_sort(conn, folder_id)
        subfolders = folders.list_children(conn, folder_id, sort)
        files = list_files(conn, folder_id, sort)
        crumbs = folders.ancestors(conn, folder_id) if folder_id else []
    return render(request, "files.html", section="files", title=current["name"] if current else "Files",
                  folder=current, crumbs=crumbs, subfolders=subfolders, files=files,
                  sort_label=folders.SORTS[sort], sort_options=sort_options(folder_id, sort))


# ---- API -----------------------------------------------------------------------------

@router.post("/api/files", status_code=201)
async def api_upload(request: Request) -> dict:
    """One file per request, raw bytes as the body, name in X-File-Name (percent-encoded)."""
    settings = request.app.state.settings
    name = storage.clean_name(unquote(request.headers.get("x-file-name", "")))
    folder_id = folder_query(request)

    def folder_exists() -> bool:
        with db.connect(settings.db_path) as conn:
            return folders.get_folder(conn, folder_id) is not None

    # Checked before the bytes arrive, so a 2 GB upload doesn't stream into nowhere.
    if folder_id is not None and not await run_in_threadpool(folder_exists):
        raise ApiError(folders.NOT_FOUND, 404)
    file_id, size, sha256 = await storage.receive_upload(request, settings.data_dir, settings.max_upload_size_mb)

    def insert() -> dict:
        with db.connect(settings.db_path) as conn:
            return insert_file(conn, file_id, name, size, sha256, folder_id)

    try:
        file = await run_in_threadpool(insert)
    except BaseException:
        storage.remove(settings.files_dir, file_id)
        raise
    log.info("File %s uploaded (%d bytes)", file_id, size)
    return file


def folder_query(request: Request) -> int | None:
    try:
        return folders.parse_folder_param(request.query_params.get("folder_id"))
    except ValueError:
        raise ApiError(folders.NOT_FOUND, 404) from None


@router.get("/api/files")
def api_list(request: Request, sort: str | None = None) -> dict:
    """One folder's contents (?folder_id=, empty for the top level), in its saved sort unless
    `sort` is given. Doesn't save the sort; the page does."""
    folder_id = folder_query(request)
    with db.connect(request.app.state.settings.db_path) as conn:
        if folder_id is not None and folders.get_folder(conn, folder_id) is None:
            raise ApiError(folders.NOT_FOUND, 404)
        sort = sort if sort in folders.SORTS else folders.get_sort(conn, folder_id)
        subfolders = [{k: v for k, v in f.items() if k != "items"} for f in folders.list_children(conn, folder_id, sort)]
        return {"folders": subfolders, "files": list_files(conn, folder_id, sort)}


@router.patch("/api/files/{file_id}")
def api_update(request: Request, file_id: str, payload: dict = Body(...)) -> dict:
    fields = check_fields(payload, {"name", "favorite", "folder_id"})
    file = None
    if valid_id(file_id):
        with db.connect(request.app.state.settings.db_path) as conn:
            file = update_file(conn, file_id, fields)
    if file is None:
        raise ApiError(NOT_FOUND, 404)
    return file


@router.delete("/api/files/{file_id}", status_code=204)
def api_delete(request: Request, file_id: str) -> Response:
    """Row first, in its own transaction, then the bytes: a crash in between leaves an orphan
    file on disk, never a row pointing at nothing (TECH_PLAN §5 #20)."""
    settings = request.app.state.settings
    deleted = False
    if valid_id(file_id):
        with db.connect(settings.db_path) as conn:
            deleted = delete_file_row(conn, file_id)
    if not deleted:
        raise ApiError(NOT_FOUND, 404)
    storage.remove(settings.files_dir, file_id)
    log.info("File %s deleted", file_id)
    return Response(status_code=204)


async def file_response(request: Request, file_id: str, inline: bool) -> Response:
    settings = request.app.state.settings

    def lookup() -> dict | None:
        with db.connect(settings.db_path) as conn:
            return get_file(conn, file_id)

    file = await run_in_threadpool(lookup) if valid_id(file_id) else None
    if file is None:
        raise ApiError(NOT_FOUND, 404)
    path = storage.path_for(settings.files_dir, file_id)
    if not path.is_file():
        log.warning("File %s is in the database but missing from disk", file_id)
        raise ApiError("This file is missing from the vault's disk.", 404)

    content_type = storage.inline_type(file["name"]) if inline else None
    headers = {"Cache-Control": "private, no-cache", "Content-Security-Policy": FILE_CSP}
    if content_type == "application/pdf":
        headers.update({"Content-Security-Policy": PDF_CSP, "X-Frame-Options": "SAMEORIGIN"})
    return FileResponse(
        path,
        media_type=content_type or file["mime"],
        filename=file["name"],
        content_disposition_type="inline" if content_type else "attachment",
        headers=headers,
    )


@router.get("/api/files/{file_id}/download")
async def api_download(request: Request, file_id: str) -> Response:
    return await file_response(request, file_id, inline=False)


@router.get("/api/files/{file_id}/view")
async def api_view(request: Request, file_id: str) -> Response:
    """Inline only for the allowlist in storage.INLINE; everything else downloads."""
    return await file_response(request, file_id, inline=True)
