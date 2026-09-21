"""Home, Favorites, Search (S9) and Settings (S3): the pages that show every type at once.

Mixed lists are (kind, item) pairs, rendered by macros.any_row with each type's own row.
The per-type queries stay in their modules; this one only combines them.
"""
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from starlette.responses import Response

from app import VERSION, auth, clips, db, files, folders, links, notes
from app.web import SECTIONS, render

router = APIRouter()

HOME_FAVORITES = 6
RECENT = 10
SEARCH_LIMIT = 20
# Result groups, in page order. "files" also holds folders.
TYPES = {"files": "Files", "notes": "Notes", "clips": "Clips", "links": "Links"}
# Search opened from a section starts narrowed to that section's type (DESIGN §3.12).
SECTION_TYPES = {"files": "files", "photos": "files", "notes": "notes", "clipboard": "clips", "links": "links"}


# ---- SQL -----------------------------------------------------------------------------

def vault_counts(conn) -> dict:
    row = conn.execute(
        "SELECT (SELECT COUNT(*) FROM files) AS files, (SELECT COALESCE(SUM(size), 0) FROM files) AS used,"
        " (SELECT COUNT(*) FROM notes) AS notes, (SELECT COUNT(*) FROM clips) AS clips,"
        " (SELECT COUNT(*) FROM links) AS links"
    ).fetchone()
    return dict(row)


def favorite_groups(conn) -> dict[str, list[tuple[str, dict]]]:
    """Every favorite, grouped by type, newest-modified first within each."""
    def rows(table: str, columns: str, to_item, kind: str) -> list[tuple[str, dict]]:
        sql = f"SELECT {columns} FROM {table} WHERE favorite = 1 ORDER BY updated_at DESC, rowid DESC"
        return [(kind, to_item(row)) for row in conn.execute(sql)]

    return {
        "files": rows("files", files.COLUMNS, files.to_file, "file"),
        "notes": rows("notes", notes.COLUMNS, notes.to_note, "note"),
        "clips": rows("clips", clips.COLUMNS, clips.to_clip, "clip"),
        "links": rows("links", links.COLUMNS, links.to_link, "link"),
    }


def home_favorites(groups: dict) -> list[tuple[str, dict]]:
    """Home shows six: clips first (Home answers "what can I copy"), then the rest, newest first."""
    rest = sorted(groups["files"] + groups["notes"] + groups["links"], key=lambda pair: pair[1]["updated_at"], reverse=True)
    return (groups["clips"] + rest)[:HOME_FAVORITES]


def recent(conn) -> list[tuple[str, dict]]:
    """The ten newest things of any type: files and links by when they were added, notes and
    clips by when they were last edited. Empty notes and clips are left out, as in their lists."""
    items = [("file", f, f["created_at"]) for f in (files.to_file(row) for row in conn.execute(
        f"SELECT {files.COLUMNS} FROM files ORDER BY created_at DESC, rowid DESC LIMIT ?", (RECENT,)))]
    items += [("note", n, n["updated_at"]) for n in (notes.to_note(row) for row in conn.execute(
        f"SELECT {notes.COLUMNS} FROM notes WHERE title != '' OR body != '' ORDER BY updated_at DESC, id DESC LIMIT ?",
        (RECENT,)))]
    items += [("clip", c, c["updated_at"]) for c in (clips.to_clip(row) for row in conn.execute(
        f"SELECT {clips.COLUMNS} FROM clips WHERE title != '' OR content != '' ORDER BY updated_at DESC, id DESC LIMIT ?",
        (RECENT,)))]
    items += [("link", link, link["created_at"]) for link in (links.to_link(row) for row in conn.execute(
        f"SELECT {links.COLUMNS} FROM links ORDER BY created_at DESC, id DESC LIMIT ?", (RECENT,)))]
    items.sort(key=lambda item: item[2], reverse=True)
    return [(kind, item) for kind, item, _ in items[:RECENT]]


def search(conn, q: str, kind: str | None = None) -> dict[str, list[dict]]:
    """Up to 20 of each type whose text contains `q` (case-insensitive for ASCII, % and _ literal).
    `kind` narrows to one of TYPES. Hidden clips match by title only (clips.list_clips)."""
    q = q.strip()
    wanted = TYPES if kind is None else {kind}
    empty: list[dict] = []
    return {
        "folders": folders.search_folders(conn, q, SEARCH_LIMIT) if q and "files" in wanted else empty,
        "files": files.search_files(conn, q, SEARCH_LIMIT) if q and "files" in wanted else empty,
        "notes": notes.list_notes(conn, q)[:SEARCH_LIMIT] if q and "notes" in wanted else empty,
        "clips": clips.list_clips(conn, q)[:SEARCH_LIMIT] if q and "clips" in wanted else empty,
        "links": links.list_links(conn, q)[:SEARCH_LIMIT] if q and "links" in wanted else empty,
    }


def snippet(text: str, q: str) -> str:
    """The note text around the first match, on one line: "…due on the 5th, electricity bill…"."""
    at = text.lower().find(q.lower())
    if at < 0:
        return ""
    start, end = max(0, at - 30), min(len(text), at + len(q) + 60)
    line = " ".join(text[start:end].split())
    return ("…" if start else "") + line + ("…" if end < len(text) else "")


def result_groups(found: dict, q: str) -> list[tuple[str, str, list]]:
    """(key, label, [(kind, item, snippet)]) for the page, in TYPES order, empty groups dropped."""
    groups = [
        ("files", [("folder", f, None) for f in found["folders"]] + [("file", f, None) for f in found["files"]]),
        ("notes", [("note", n, snippet(n["body"], q) or None) for n in found["notes"]]),
        ("clips", [("clip", c, None) for c in found["clips"]]),
        ("links", [("link", link, None) for link in found["links"]]),
    ]
    return [(key, TYPES[key], rows) for key, rows in groups if rows]


# ---- Pages ---------------------------------------------------------------------------

@router.get("/")
def home_page(request: Request) -> Response:
    with db.connect(request.app.state.settings.db_path) as conn:
        groups = favorite_groups(conn)
        latest = recent(conn)
    count = sum(len(rows) for rows in groups.values())
    return render(request, "home.html", section="home", title="My Vault",
                  favorites=home_favorites(groups), favorite_count=count, recent=latest)


@router.get("/favorites")
def favorites_page(request: Request, type: str | None = None) -> Response:
    """Every favorite, grouped by type; ?type= shows one group."""
    kind = type if type in TYPES else None
    with db.connect(request.app.state.settings.db_path) as conn:
        groups = favorite_groups(conn)
    total = sum(len(rows) for rows in groups.values())
    shown = [(key, TYPES[key], [(k, item, None) for k, item in groups[key]])
             for key in TYPES if groups[key] and kind in (None, key)]
    return render(request, "favorites.html", section="favorites", title="Favorites",
                  groups=shown, total=total, kind=kind, types=TYPES)


@router.get("/search")
def search_page(request: Request, q: str = "", type: str | None = None) -> Response:
    """Results grouped by type, live via ?partial=1 as you type. `in=<section>` (the search icon
    on a section's page) starts narrowed to that section; type=all widens it."""
    came_from = request.query_params.get("in")
    kind = type if type in TYPES else None
    if type is None and came_from in SECTION_TYPES:
        kind = SECTION_TYPES[came_from]
    q = q.strip()[:200]
    with db.connect(request.app.state.settings.db_path) as conn:
        found = search(conn, q, kind)
    back = next((href for key, href, _, _ in SECTIONS if key == came_from), "/")
    return render(request, "search.html", section="search", title="Search", q=q, kind=kind, types=TYPES,
                  groups=result_groups(found, q), back=back)


# ---- API -----------------------------------------------------------------------------

@router.get("/api/search")
def api_search(request: Request, q: str = "", type: str | None = None) -> dict:
    """{folders, files, notes, clips, links}, each at most 20. A hidden clip's content is blanked."""
    with db.connect(request.app.state.settings.db_path) as conn:
        found = search(conn, q[:200], type if type in TYPES else None)
    found["clips"] = [{**clip, "content": ""} if clip["hidden"] else clip for clip in found["clips"]]
    for folder in found["folders"]:
        folder.pop("items")
    return found


# ---- Settings ------------------------------------------------------------------------

def last_backup_text(settings) -> str:
    """Newest DB snapshot written by the backup (S10), shown in VAULT_TIMEZONE."""
    snapshots = [p for p in (settings.backup_dir / "db").glob("vault-*.db") if not p.stem.endswith("-INCOMPLETE")]
    if not snapshots:
        return "Never"
    newest = max(snapshot.stat().st_mtime for snapshot in snapshots)
    return datetime.fromtimestamp(newest, ZoneInfo(settings.timezone)).strftime("%b %-d, %H:%M")


@router.get("/settings")
def settings_page(request: Request) -> Response:
    settings = request.app.state.settings
    with db.connect(settings.db_path) as conn:
        counts = vault_counts(conn)
    return render(
        request, "settings.html", section="settings", title="Settings",
        counts=counts, free=shutil.disk_usage(settings.data_dir).free,
        version=VERSION, last_backup=last_backup_text(settings),
        min_password_length=auth.MIN_PASSWORD_LENGTH,
    )
