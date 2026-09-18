"""Folders: a parent_id tree in the database, plus moving and deleting many items at once (S7).

Folders exist only as rows. Renaming or moving never touches a file on disk; deleting removes
the rows first, then the bytes of every file that was inside (TECH_PLAN §2).
"""
import logging
import re
import sqlite3

from fastapi import APIRouter, Body, Request
from starlette.responses import Response

from app import db, storage, thumbs
from app.web import ApiError

log = logging.getLogger("vault.folders")
router = APIRouter()

COLUMNS = "id, parent_id, name, sort, created_at, updated_at"
NOT_FOUND = "That folder no longer exists."
GONE = "Some of those items no longer exist. Reload the page and try again."
MAX_ITEMS = 1000

# "-" means descending. The first tap on a sort picks its natural direction: names A→Z,
# dates and sizes biggest/newest first. Tapping it again flips (TECH_PLAN §9).
SORTS = {
    "name": "Name A–Z", "-name": "Name Z–A",
    "-date": "Newest first", "date": "Oldest first",
    "-size": "Largest first", "size": "Smallest first",
    "type": "Type A–Z", "-type": "Type Z–A",
}
SORT_CHOICES = [("name", "Name", "name"), ("date", "Date added", "-date"),
                ("size", "Size", "-size"), ("type", "Type", "type")]

# ORDER BY clauses for each sort key. {d} is ASC or DESC; nothing here comes from a request.
FILE_ORDER = {
    "name": "name COLLATE NOCASE {d}, rowid {d}",
    "date": "created_at {d}, rowid {d}",
    "size": "size {d}, name COLLATE NOCASE, rowid",
    "type": "kind {d}, mime {d}, name COLLATE NOCASE, rowid",
}
# Folders have no size or type: they keep name order for those, in the chosen direction.
FOLDER_ORDER = {
    "name": "name COLLATE NOCASE {d}, id",
    "date": "created_at {d}, id {d}",
    "size": "name COLLATE NOCASE, id",
    "type": "name COLLATE NOCASE {d}, id",
}

# Every folder id under (and including) the ids in `marks`. UNION, not UNION ALL, so even a
# broken tree can't loop.
SUBTREE = ("WITH RECURSIVE down(id) AS (SELECT id FROM folders WHERE id IN ({marks})"
           " UNION SELECT f.id FROM folders f JOIN down ON f.parent_id = down.id) ")


# ---- SQL -----------------------------------------------------------------------------

def marks(values) -> str:
    return ", ".join("?" * len(values))


def order_by(table: dict, sort: str) -> str:
    return table[sort.lstrip("-")].format(d="DESC" if sort.startswith("-") else "ASC")


def get_folder(conn, folder_id: int) -> dict | None:
    row = conn.execute(f"SELECT {COLUMNS} FROM folders WHERE id = ?", (folder_id,)).fetchone()
    return dict(row) if row else None


def list_all(conn) -> list[dict]:
    """The whole tree, for the move picker."""
    return [dict(row) for row in conn.execute(f"SELECT {COLUMNS} FROM folders ORDER BY name COLLATE NOCASE, id")]


def list_children(conn, parent_id: int | None, sort: str) -> list[dict]:
    """Sub-folders of one folder, each with `items`: how many folders and files sit directly in it."""
    rows = conn.execute(
        f"SELECT {COLUMNS},"
        " (SELECT COUNT(*) FROM folders c WHERE c.parent_id = folders.id)"
        " + (SELECT COUNT(*) FROM files WHERE files.folder_id = folders.id) AS items"
        f" FROM folders WHERE parent_id IS ? ORDER BY {order_by(FOLDER_ORDER, sort)}",
        (parent_id,),
    )
    return [dict(row) for row in rows]


def search_folders(conn, q: str, limit: int) -> list[dict]:
    """Folders whose name contains `q` (LIKE, escaped), with `items` like list_children."""
    rows = conn.execute(
        f"SELECT {COLUMNS},"
        " (SELECT COUNT(*) FROM folders c WHERE c.parent_id = folders.id)"
        " + (SELECT COUNT(*) FROM files WHERE files.folder_id = folders.id) AS items"
        " FROM folders WHERE name LIKE ? ESCAPE '\\' ORDER BY name COLLATE NOCASE, id LIMIT ?",
        (db.like_pattern(q), limit),
    )
    return [dict(row) for row in rows]


def ancestors(conn, folder_id: int) -> list[dict]:
    """[{id, name}] from the top level down to this folder, for the breadcrumb."""
    rows = conn.execute(
        "WITH RECURSIVE up(id, parent_id, name, depth) AS ("
        " SELECT id, parent_id, name, 0 FROM folders WHERE id = ?"
        " UNION ALL SELECT f.id, f.parent_id, f.name, up.depth + 1 FROM folders f JOIN up ON f.id = up.parent_id"
        " WHERE up.depth < 1000)"
        " SELECT id, name FROM up ORDER BY depth DESC",
        (folder_id,),
    )
    return [dict(row) for row in rows]


def subtree_ids(conn, folder_ids: list[int]) -> set[int]:
    if not folder_ids:
        return set()
    sql = SUBTREE.format(marks=marks(folder_ids)) + "SELECT id FROM down"
    return {row[0] for row in conn.execute(sql, folder_ids)}


def get_sort(conn, folder_id: int | None) -> str:
    """The sort saved on a folder; the top level keeps its own in settings."""
    if folder_id is None:
        row = conn.execute("SELECT value FROM settings WHERE key = 'files_sort'").fetchone()
        return row[0] if row and row[0] in SORTS else "name"
    return conn.execute("SELECT sort FROM folders WHERE id = ?", (folder_id,)).fetchone()[0]


def save_sort(conn, folder_id: int | None, sort: str) -> None:
    if folder_id is None:
        conn.execute("INSERT INTO settings (key, value) VALUES ('files_sort', ?)"
                     " ON CONFLICT (key) DO UPDATE SET value = excluded.value", (sort,))
    else:
        conn.execute("UPDATE folders SET sort = ? WHERE id = ?", (sort, folder_id))


def summary(conn, folder_id: int) -> dict:
    """What deleting this folder removes: the folders under it (not itself), files, bytes."""
    down = SUBTREE.format(marks="?")
    folders = conn.execute(down + "SELECT COUNT(*) - 1 FROM down", (folder_id,)).fetchone()[0]
    files, size = conn.execute(
        down + "SELECT COUNT(*), COALESCE(SUM(size), 0) FROM files WHERE folder_id IN (SELECT id FROM down)",
        (folder_id,),
    ).fetchone()
    return {"folders": folders, "files": files, "size": size}


def check_parent(conn, parent_id: int | None) -> None:
    if parent_id is not None and get_folder(conn, parent_id) is None:
        raise ApiError(NOT_FOUND, 404)


def duplicate(name: str) -> ApiError:
    return ApiError(f"There's already a folder called “{name}” there.", 409)


def create_folder(conn, name: str, parent_id: int | None) -> dict:
    check_parent(conn, parent_id)
    now = db.now()
    try:
        cursor = conn.execute(
            "INSERT INTO folders (parent_id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (parent_id, name, now, now),
        )
    except sqlite3.IntegrityError:
        raise duplicate(name) from None
    return get_folder(conn, cursor.lastrowid)


def update_folder(conn, folder_id: int, fields: dict) -> dict | None:
    """Rename and/or move. A rename counts as modified; a move doesn't."""
    folder = get_folder(conn, folder_id)
    if folder is None:
        return None
    if "parent_id" in fields:
        check_parent(conn, fields["parent_id"])
        if fields["parent_id"] in subtree_ids(conn, [folder_id]):
            raise ApiError("A folder can't go inside itself.", 422)
    if fields:
        assignments = [f"{name} = ?" for name in fields]
        params = list(fields.values())
        if "name" in fields:
            assignments.append("updated_at = ?")
            params.append(db.now())
        try:
            conn.execute(f"UPDATE folders SET {', '.join(assignments)} WHERE id = ?", (*params, folder_id))
        except sqlite3.IntegrityError:
            raise duplicate(fields.get("name", folder["name"])) from None
    return get_folder(conn, folder_id)


def move_items(conn, file_ids: list[str], folder_ids: list[int], to: int | None) -> int:
    """All or nothing: any problem raises, and db.connect() rolls every change back."""
    check_parent(conn, to)
    file_ids, folder_ids = list(dict.fromkeys(file_ids)), list(dict.fromkeys(folder_ids))
    if file_ids:
        found = conn.execute(f"SELECT COUNT(*) FROM files WHERE id IN ({marks(file_ids)})", file_ids).fetchone()[0]
        if found != len(file_ids):
            raise ApiError(GONE, 404)
    if folder_ids:
        found = conn.execute(f"SELECT COUNT(*) FROM folders WHERE id IN ({marks(folder_ids)})", folder_ids).fetchone()[0]
        if found != len(folder_ids):
            raise ApiError(GONE, 404)
        if to is not None and to in subtree_ids(conn, folder_ids):
            raise ApiError("A folder can't go inside itself.", 422)
    if file_ids:
        conn.execute(f"UPDATE files SET folder_id = ? WHERE id IN ({marks(file_ids)})", (to, *file_ids))
    for folder_id in folder_ids:
        try:
            conn.execute("UPDATE folders SET parent_id = ? WHERE id = ?", (to, folder_id))
        except sqlite3.IntegrityError:
            raise duplicate(get_folder(conn, folder_id)["name"]) from None
    return len(file_ids) + len(folder_ids)


def delete_items(conn, file_ids: list[str], folder_ids: list[int]) -> tuple[int, list[str]]:
    """Delete the rows of these files and folders, and of everything inside the folders.
    Returns (folders deleted, ids of files deleted); the caller removes the bytes after the
    transaction commits. Ids that no longer exist are skipped: gone is what was asked for."""
    folder_ids = list(dict.fromkeys(folder_ids))
    inside: list[str] = []
    folders = 0
    if folder_ids:
        down = SUBTREE.format(marks=marks(folder_ids))
        inside = [row[0] for row in conn.execute(
            down + "SELECT id FROM files WHERE folder_id IN (SELECT id FROM down)", folder_ids)]
        folders = conn.execute(down + "SELECT COUNT(*) FROM down", folder_ids).fetchone()[0]
    direct: list[str] = []
    if file_ids:
        direct = [row[0] for row in conn.execute(
            f"SELECT id FROM files WHERE id IN ({marks(file_ids)})", file_ids)]
    if direct:
        conn.execute(f"DELETE FROM files WHERE id IN ({marks(direct)})", direct)
    if folder_ids:
        # ON DELETE CASCADE takes the file rows inside with them.
        conn.execute(SUBTREE.format(marks=marks(folder_ids)) + "DELETE FROM folders WHERE id IN (SELECT id FROM down)",
                     folder_ids)
    return folders, list(dict.fromkeys(direct + inside))


def is_id(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def check_fields(payload: dict, allowed: set[str]) -> dict:
    """Validate a folder body. Raises ApiError with a sentence the user can act on."""
    if not payload.keys() <= allowed:
        raise ApiError("That request wasn't understood.", 422)
    fields = dict(payload)
    if "name" in fields:
        if not isinstance(fields["name"], str):
            raise ApiError("That request wasn't understood.", 422)
        if not fields["name"].strip(" ."):
            raise ApiError("Enter a name.", 422)
        fields["name"] = storage.clean_name(fields["name"])
    if "parent_id" in fields and not (fields["parent_id"] is None or is_id(fields["parent_id"])):
        raise ApiError("That request wasn't understood.", 422)
    return fields


def check_items(payload: dict, allowed: set[str]) -> tuple[list[str], list[int]]:
    """The {files: [id], folders: [id]} part of a move or delete."""
    if not payload.keys() <= allowed:
        raise ApiError("That request wasn't understood.", 422)
    file_ids, folder_ids = payload.get("files", []), payload.get("folders", [])
    if (not isinstance(file_ids, list) or not isinstance(folder_ids, list)
            or not all(isinstance(i, str) and storage.ID_PATTERN.fullmatch(i) for i in file_ids)
            or not all(is_id(i) for i in folder_ids)):
        raise ApiError("That request wasn't understood.", 422)
    if not file_ids and not folder_ids:
        raise ApiError("Select something first.", 422)
    if len(file_ids) + len(folder_ids) > MAX_ITEMS:
        raise ApiError(f"That's too many items at once (max {MAX_ITEMS:,}).", 422)
    return file_ids, folder_ids


def parse_folder_param(value: str | None) -> int | None:
    """?folder= / ?folder_id=: missing or empty is the top level. Raises ValueError for
    anything that isn't a folder id."""
    if value in (None, ""):
        return None
    if not re.fullmatch(r"[1-9][0-9]{0,17}", value):
        raise ValueError("not a folder id")
    return int(value)


def remove_files(settings, file_ids: list[str]) -> None:
    for file_id in file_ids:
        storage.remove(settings.files_dir, file_id)
        thumbs.remove(settings.thumbs_dir, file_id)


# ---- API -----------------------------------------------------------------------------

@router.get("/api/folders")
def api_list(request: Request) -> dict:
    with db.connect(request.app.state.settings.db_path) as conn:
        return {"folders": list_all(conn)}


@router.post("/api/folders", status_code=201)
def api_create(request: Request, payload: dict = Body(...)) -> dict:
    fields = check_fields(payload, {"name", "parent_id"})
    if "name" not in fields:
        raise ApiError("Enter a name.", 422)
    with db.connect(request.app.state.settings.db_path) as conn:
        folder = create_folder(conn, fields["name"], fields.get("parent_id"))
    log.info("Folder %d created", folder["id"])
    return folder


@router.patch("/api/folders/{folder_id:int}")
def api_update(request: Request, folder_id: int, payload: dict = Body(...)) -> dict:
    fields = check_fields(payload, {"name", "parent_id"})
    with db.connect(request.app.state.settings.db_path) as conn:
        folder = update_folder(conn, folder_id, fields)
    if folder is None:
        raise ApiError(NOT_FOUND, 404)
    log.info("Folder %d updated", folder_id)
    return folder


@router.get("/api/folders/{folder_id:int}/summary")
def api_summary(request: Request, folder_id: int) -> dict:
    with db.connect(request.app.state.settings.db_path) as conn:
        if get_folder(conn, folder_id) is None:
            raise ApiError(NOT_FOUND, 404)
        return summary(conn, folder_id)


@router.delete("/api/folders/{folder_id:int}", status_code=204)
def api_delete(request: Request, folder_id: int) -> Response:
    settings = request.app.state.settings
    with db.connect(settings.db_path) as conn:
        if get_folder(conn, folder_id) is None:
            raise ApiError(NOT_FOUND, 404)
        folders, file_ids = delete_items(conn, [], [folder_id])
    remove_files(settings, file_ids)
    log.info("Folder %d deleted (%d folders, %d files)", folder_id, folders, len(file_ids))
    return Response(status_code=204)


@router.post("/api/move")
def api_move(request: Request, payload: dict = Body(...)) -> dict:
    if "to" not in payload or not (payload["to"] is None or is_id(payload["to"])):
        raise ApiError("That request wasn't understood.", 422)
    file_ids, folder_ids = check_items(payload, {"files", "folders", "to"})
    with db.connect(request.app.state.settings.db_path) as conn:
        moved = move_items(conn, file_ids, folder_ids, payload["to"])
    log.info("Moved %d files and %d folders to folder %s", len(set(file_ids)), len(set(folder_ids)), payload["to"])
    return {"moved": moved}


@router.post("/api/delete")
def api_delete_many(request: Request, payload: dict = Body(...)) -> dict:
    file_ids, folder_ids = check_items(payload, {"files", "folders"})
    settings = request.app.state.settings
    with db.connect(settings.db_path) as conn:
        folders, deleted_files = delete_items(conn, file_ids, folder_ids)
    remove_files(settings, deleted_files)
    log.info("Deleted %d folders and %d files", folders, len(deleted_files))
    return {"deleted": {"folders": folders, "files": len(deleted_files)}}
