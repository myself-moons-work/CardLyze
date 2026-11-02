"""Security middleware enforcing strict headers across all responses."""

from typing import Callable
from starlette.types import ASGIApp, Receive, Scope, Send

SECURITY_HEADERS = [
    (b"cache-control", b"no-store"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-content-type-options", b"nosniff"),
    (b"content-security-policy", b"default-src 'self'"),
]


class SecurityHeadersMiddleware:
    """ASGI middleware injecting security and privacy headers on every HTTP response."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing_keys = {h[0].lower() for h in SECURITY_HEADERS}
                filtered_headers = [
                    (k, v) for k, v in headers if k.lower() not in existing_keys
                ]
                filtered_headers.extend(SECURITY_HEADERS)
                message["headers"] = filtered_headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

