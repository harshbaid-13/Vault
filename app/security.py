"""Security middleware. S1: response headers. S2 adds the auth gate, Origin check and login limiter."""
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
    """Plain ASGI, not BaseHTTPMiddleware, so large streamed responses pass straight through."""

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
