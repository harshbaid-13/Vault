"""The application: middleware, routes, error pages."""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app import db
from app.config import Settings
from app.security import SecurityHeadersMiddleware, add_security_headers
from app.web import render

log = logging.getLogger("vault")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# S1 placeholder pages: path → (section, title, icon, stage that builds it).
PLACEHOLDERS = {
    "/": ("home", "My Vault", "house", "S9"),
    "/files": ("files", "Files", "folder", "S6"),
    "/photos": ("photos", "Photos", "image", "S8"),
    "/notes": ("notes", "Notes", "file-text", "S5"),
    "/clipboard": ("clipboard", "Clipboard", "clipboard", "S4"),
    "/links": ("links", "Links", "link", "S5"),
    "/favorites": ("favorites", "Favorites", "star", "S9"),
    "/search": ("search", "Search", "search", "S9"),
    "/settings": ("settings", "Settings", "settings", "S3"),
}

ERROR_PAGES = {
    404: ("Not found", "This page doesn't exist. It may have been deleted, or the link is wrong."),
    500: ("Something went wrong", "The vault hit an error. Try again; if it keeps happening, check the app logs."),
}


def wants_json(request: Request) -> bool:
    return request.url.path.startswith("/api/") or request.url.path == "/healthz"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    version = db.prepare(settings)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/healthz")
    def healthz() -> dict:
        with db.connect(settings.db_path) as conn:
            conn.execute("SELECT 1")
        return {"ok": True}

    for path, (section, title, icon, stage) in PLACEHOLDERS.items():
        app.add_api_route(path, placeholder(section, title, icon, stage), methods=["GET"], response_class=HTMLResponse)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        title, message = ERROR_PAGES.get(exc.status_code, ("Something went wrong", "That request didn't work."))
        if wants_json(request):
            return JSONResponse({"error": message}, status_code=exc.status_code, headers=exc.headers)
        return render(request, "error.html", status_code=exc.status_code, title=title, message=message)

    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception) -> Response:
        # The type only: an exception message can carry note or clip text.
        log.error("Unhandled %s on %s %s", type(exc).__name__, request.method, request.url.path)
        title, message = ERROR_PAGES[500]
        if wants_json(request):
            response = JSONResponse({"error": message}, status_code=500)
        else:
            response = render(request, "error.html", status_code=500, title=title, message=message)
        # This handler runs outside the middleware stack, so add the headers here too.
        add_security_headers(MutableHeaders(raw=response.raw_headers))
        return response

    log.info("Vault ready: data in %s, schema version %d", settings.data_dir, version)
    return app


def placeholder(section: str, title: str, icon: str, stage: str):
    def page(request: Request) -> Response:
        label = "Home" if section == "home" else title
        return render(request, "placeholder.html", section=section, title=title, label=label, icon=icon, stage=stage)

    page.__name__ = f"placeholder_{section}"
    return page
