"""Home, Favorites, Search (S9) and Settings (S3).

S3: only /settings lives here so far.
"""
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Request
from starlette.responses import Response

from app import VERSION, auth, db
from app.web import render

router = APIRouter()


# ---- SQL -----------------------------------------------------------------------------

def vault_counts(conn) -> dict:
    row = conn.execute(
        "SELECT (SELECT COUNT(*) FROM files) AS files, (SELECT COALESCE(SUM(size), 0) FROM files) AS used,"
        " (SELECT COUNT(*) FROM notes) AS notes, (SELECT COUNT(*) FROM clips) AS clips,"
        " (SELECT COUNT(*) FROM links) AS links"
    ).fetchone()
    return dict(row)


# ---- Pages ---------------------------------------------------------------------------

def last_backup_text(settings) -> str:
    """Newest DB snapshot written by the backup (S10), shown in VAULT_TIMEZONE."""
    snapshots = list((settings.backup_dir / "db").glob("vault-*.db"))
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
