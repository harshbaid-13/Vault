"""Security middleware: response headers, the auth gate, the Origin check, and the login limiter.

All plain ASGI, not BaseHTTPMiddleware, so large streamed requests and responses pass straight
through.
"""
import threading
import time
from collections.abc import Callable
from urllib.parse import quote, urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.gzip import GZipMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.web import render

CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self'",
    "media-src 'self'",
    "frame-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
}


def add_security_headers(headers: MutableHeaders) -> None:
    """Fill in any header a route hasn't set itself (file routes set their own CSP in S6)."""
    for name, value in HEADERS.items():
        headers.setdefault(name, value)
    # Pages can hold hidden clip content: never keep a copy in a cache (TECH_PLAN §5 #17).
    if headers.get("content-type", "").startswith("text/html"):
        headers.setdefault("Cache-Control", "no-store")


class SecurityHeadersMiddleware:

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                add_security_headers(MutableHeaders(scope=message))
            await send(message)

        await self.app(scope, receive, send_with_headers)


class CompressMiddleware:
    """Gzip pages, JSON and static text — a folder of 2,000 files is 2.3 MB of HTML and about
    250 KB gzipped, which matters over a phone connection (S11).

    Uploaded bytes are never compressed: photos, video, PDFs and zips are compressed already,
    and gzipping a response would break the byte ranges a video player asks for. Requests that
    carry a Range header skip it for the same reason.
    """

    FILE_BYTES = "/api/files/"

    def __init__(self, app: ASGIApp) -> None:
        self.plain = app
        self.compressed = GZipMiddleware(app, minimum_size=1024, compresslevel=6)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        skip = (scope["type"] != "http" or path.startswith(self.FILE_BYTES)
                or Headers(scope=scope).get("range") is not None)
        await (self.plain if skip else self.compressed)(scope, receive, send)


# ---- Login limiter --------------------------------------------------------------------

class LoginLimiter:
    """One global bucket (TECH_PLAN §8 gotcha 11): behind `tailscale serve` every request
    comes from the same address. 5 failures lock for 60 s; each further failure doubles
    the lock, up to 15 minutes. A success resets it. In memory: a restart unlocks.
    """

    FREE_FAILURES = 5
    FIRST_LOCK = 60
    MAX_LOCK = 15 * 60

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.failures = 0
        self.locked_until = 0.0
        self.lock = threading.Lock()

    def wait(self) -> int:
        """Seconds until the next attempt is allowed; 0 when it is allowed now."""
        with self.lock:
            return max(0, int(-(-(self.locked_until - self.clock()) // 1)))

    def fail(self) -> int:
        """Record a failure. Returns the lock that starts now in seconds, or 0."""
        with self.lock:
            self.failures += 1
            if self.failures < self.FREE_FAILURES:
                return 0
            seconds = min(self.FIRST_LOCK * 2 ** (self.failures - self.FREE_FAILURES), self.MAX_LOCK)
            self.locked_until = self.clock() + seconds
            return seconds

    def reset(self) -> None:
        with self.lock:
            self.failures = 0
            self.locked_until = 0.0


# ---- Origin check (CSRF) --------------------------------------------------------------

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
API_BODY_TYPES = ("application/json", "application/octet-stream")


def is_api(path: str) -> bool:
    return path.startswith("/api/")


def error_response(scope: Scope, status_code: int, title: str, message: str) -> Response:
    if is_api(scope["path"]):
        return JSONResponse({"error": message}, status_code=status_code)
    return render(Request(scope), "error.html", status_code=status_code, title=title, message=message)


class OriginCheckMiddleware:
    """Writes must come from the vault's own pages: Origin (or Referer) equal to the
    request's own origin or one of VAULT_ALLOWED_ORIGINS. `/api` writes with a body must
    also be JSON (or raw bytes, for uploads), which a plain HTML form on another site can't send.
    """

    def __init__(self, app: ASGIApp, allowed_origins: tuple[str, ...] = ()) -> None:
        self.app = app
        self.allowed_origins = set(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if not self.origin_ok(scope, headers):
            response = error_response(
                scope, 403, "Blocked",
                "This request didn't come from the vault's own pages, so it was blocked. Reload the page and try again.",
            )
            await response(scope, receive, send)
            return

        content_type = headers.get("content-type", "").split(";")[0].strip().lower()
        if is_api(scope["path"]) and scope["method"] != "DELETE" and content_type not in API_BODY_TYPES:
            response = JSONResponse({"error": "That request wasn't understood."}, status_code=415)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def origin_ok(self, scope: Scope, headers: Headers) -> bool:
        origin = headers.get("origin")
        if not origin:
            referer = headers.get("referer")
            if not referer:
                return False
            parts = urlsplit(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
        origin = origin.rstrip("/")
        own = f"{scope.get('scheme', 'http')}://{headers.get('host', '')}"
        return origin == own or origin in self.allowed_origins


# ---- Auth gate ------------------------------------------------------------------------

PUBLIC_PATHS = {"/login", "/healthz"}
PUBLIC_PREFIXES = ("/static/",)


def is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)


class AuthGateMiddleware:
    """An allowlist: every path not listed above needs a logged-in session, so a new route
    is protected without anyone remembering to protect it. Needs SessionMiddleware outside it.
    """

    def __init__(self, app: ASGIApp, is_logged_in: Callable[[dict], bool]) -> None:
        self.app = app
        self.is_logged_in = is_logged_in

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or is_public(scope["path"]) or self.is_logged_in(scope["session"]):
            await self.app(scope, receive, send)
            return

        if is_api(scope["path"]):
            response: Response = JSONResponse({"error": "You're logged out. Reload the page to log in again."}, status_code=401)
        elif scope["method"] in ("GET", "HEAD"):
            target = scope["path"]
            if scope.get("query_string"):
                target += "?" + scope["query_string"].decode("latin-1")
            location = "/login" if target == "/" else "/login?next=" + quote(target, safe="")
            response = RedirectResponse(location, status_code=302)
        else:
            response = RedirectResponse("/login", status_code=303)
        await response(scope, receive, send)
