"""Templates, filters, the navigation every page shares, and the API error type."""
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.responses import Response

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def size(num_bytes: int) -> str:
    """1536 → "1.5 KB". One decimal under 10, none above. Same rule as formatSize() in app.js."""
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            break
        value /= 1024
    if unit == "GB" and value >= 1024:
        value /= 1024
        unit = "TB"
    if unit == "B":
        return f"{int(value)} B"
    return f"{value:.1f} {unit}" if value < 10 else f"{value:.0f} {unit}"


@pass_context
def when(context, stamp: str) -> str:
    """A stored UTC stamp in VAULT_TIMEZONE: "Today, 09:15", "Yesterday, 18:02", "Sep 9, 18:02",
    "Mar 2, 2024"."""
    tz = ZoneInfo(context["request"].app.state.settings.timezone)
    moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).astimezone(tz)
    today = datetime.now(tz).date()
    clock = moment.strftime("%H:%M")
    if moment.date() == today:
        return f"Today, {clock}"
    if moment.date() == today - timedelta(days=1):
        return f"Yesterday, {clock}"
    if moment.year == today.year:
        return f"{moment.strftime('%b')} {moment.day}, {clock}"
    return f"{moment.strftime('%b')} {moment.day}, {moment.year}"


@pass_context
def ago(context, stamp: str) -> str:
    """List dates (DESIGN §5): relative for the last week, then "Sep 10" / "Mar 2, 2024"."""
    tz = ZoneInfo(context["request"].app.state.settings.timezone)
    moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).astimezone(tz)
    now = datetime.now(tz)
    seconds = (now - moment).total_seconds()
    days = (now.date() - moment.date()).days
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if days == 0:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    if moment.year == now.year:
        return f"{moment.strftime('%b')} {moment.day}"
    return f"{moment.strftime('%b')} {moment.day}, {moment.year}"


@pass_context
def month(context, stamp: str) -> str:
    """A stored UTC stamp as its month in VAULT_TIMEZONE: "September 2026"."""
    tz = ZoneInfo(context["request"].app.state.settings.timezone)
    moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).astimezone(tz)
    return moment.strftime("%B %Y")


templates.env.filters["size"] = size
templates.env.filters["month"] = month
templates.env.filters["ago"] = ago
templates.env.filters["when"] = when

# Sidebar order. (key, href, label, icon)
SECTIONS = [
    ("home", "/", "Home", "house"),
    ("files", "/files", "Files", "folder"),
    ("photos", "/photos", "Photos", "image"),
    ("notes", "/notes", "Notes", "file-text"),
    ("clipboard", "/clipboard", "Clipboard", "clipboard"),
    ("links", "/links", "Links", "link"),
    ("favorites", "/favorites", "Favorites", "star"),
]

# Sections without their own tab: the More tab shows as active on these.
MORE_SECTIONS = {"photos", "notes", "links", "favorites", "settings"}


class ApiError(Exception):
    """Raise from any /api route: becomes {"error": message} with this status (main.py)."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def render(request: Request, name: str, status_code: int = 200, **context: Any) -> Response:
    """Templates that `{% extends layout %}` answer ?partial=1 with only their content block,
    which the JS swaps into <main> after a change."""
    context.setdefault("section", None)
    context["layout"] = "partial.html" if request.query_params.get("partial") == "1" else "base.html"
    context.update(sections=SECTIONS, more_sections=MORE_SECTIONS,
                   max_upload_bytes=request.app.state.settings.max_upload_size_mb * 1024 * 1024)
    return templates.TemplateResponse(request, name, context, status_code=status_code)
