"""Access key protection for when the API is reachable from other devices.

Requests from the Mac itself (loopback) are always trusted: that covers the
Vite dev server and local use. Any other client (the iPhone) must send the
access key in the ``X-Access-Key`` header for every ``/api`` call.
"""

import ipaddress
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

ACCESS_KEY_HEADER = "X-Access-Key"
# Endpoints a locked-out client may call
PUBLIC_API_PATHS = {"/api/health"}
MINIMUM_ACCESS_KEY_LENGTH = 12


def is_loopback(host: str | None) -> bool:
    """True for 127.0.0.0/8, ::1 and ``localhost``; False for unknown clients."""
    if host is None:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_access_key_valid(provided_key: str | None, access_key: str) -> bool:
    """Constant-time comparison, so the key cannot be guessed by timing."""
    return bool(access_key) and secrets.compare_digest(
        (provided_key or "").encode("utf-8"), access_key.encode("utf-8")
    )


def validate_exposure(host: str, access_key: str) -> None:
    """Refuse to listen beyond the Mac without a strong enough access key.

    Args:
        host: Interface the server will bind to.
        access_key: Configured access key (may be empty).

    Raises:
        SystemExit: If the host is not loopback and the key is missing or short.
    """
    if is_loopback(host):
        return
    if len(access_key) < MINIMUM_ACCESS_KEY_LENGTH:
        raise SystemExit(
            f"FIN_TRACKER_HOST={host} exposes your finances to the network: set "
            f"FIN_TRACKER_ACCESS_KEY in .env (at least {MINIMUM_ACCESS_KEY_LENGTH} characters)."
        )


class AccessKeyMiddleware(BaseHTTPMiddleware):
    """Reject non-loopback ``/api`` calls without the right access key."""

    def __init__(self, app, access_key: str) -> None:
        super().__init__(app)
        self.access_key = access_key

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Let the request through, or answer 401."""
        path = request.url.path
        is_protected = path.startswith("/api") and path not in PUBLIC_API_PATHS
        client_host = request.client.host if request.client else None
        if (
            is_protected
            and not is_loopback(client_host)
            and not is_access_key_valid(
                request.headers.get(ACCESS_KEY_HEADER), self.access_key
            )
        ):
            return JSONResponse({"detail": "Access key required"}, status_code=401)
        return await call_next(request)
