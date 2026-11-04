from collections.abc import Awaitable, Callable

from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none';"
        return response


class CrossOriginBlockMiddleware:
    """Refuse CORS for a path prefix, whatever the app-wide CORS policy says.

    Must wrap CORSMiddleware so it can answer preflights first and strip the
    allow headers CORSMiddleware adds to regular responses.
    """

    def __init__(self, app: ASGIApp, path_prefix: str) -> None:
        self.app = app
        self.path_prefix = path_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith(self.path_prefix):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if (
            scope["method"] == "OPTIONS"
            and "origin" in headers
            and "access-control-request-method" in headers
        ):
            response = PlainTextResponse(
                "Cross-origin requests are not allowed", status_code=403
            )
            await response(scope, receive, send)
            return

        async def send_without_cors_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [
                    (name, value)
                    for name, value in message["headers"]
                    if not name.lower().startswith(b"access-control-")
                ]
            await send(message)

        await self.app(scope, receive, send_without_cors_headers)


class CookieCSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self.allowed_origins = set(allowed_origins) - {"*", "null"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        uses_session_cookie = bool(
            request.cookies.get("access_token") or request.cookies.get("refresh_token")
        )
        # refresh and logout use cookies even when an authorization header is present
        uses_cookie_auth = uses_session_cookie and (
            not request.headers.get("Authorization")
            or request.url.path in {"/v1/auth/refresh", "/v1/auth/logout"}
        )
        if request.method not in {"GET", "HEAD", "OPTIONS"} and uses_cookie_auth:
            origin = request.headers.get("Origin")
            same_origin = f"{request.url.scheme}://{request.url.netloc}"
            if origin != same_origin and origin not in self.allowed_origins:
                return JSONResponse(
                    {"detail": "CSRF origin check failed"}, status_code=403
                )
        return await call_next(request)
