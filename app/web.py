"""Templates and the navigation every page shares."""
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates
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


templates.env.filters["size"] = size

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


def render(request: Request, name: str, status_code: int = 200, **context: Any) -> Response:
    context.setdefault("section", None)
    context.update(sections=SECTIONS, more_sections=MORE_SECTIONS)
    return templates.TemplateResponse(request, name, context, status_code=status_code)
