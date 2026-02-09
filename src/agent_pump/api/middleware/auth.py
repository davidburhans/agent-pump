"""Authentication middleware for API access control."""

import logging
import secrets
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Basic API key authentication middleware.

    Validates X-API-Key header against configured key.
    Can be configured to bypass auth for specific paths (e.g., /health).
    """

    def __init__(
        self,
        app: Any,
        api_key: str,
        protected_prefixes: list[str] | None = None,
        bypass_prefixes: list[str] | None = None,
    ) -> None:
        """Initialize the auth middleware.

        Args:
            app: The ASGI application.
            api_key: The expected API key for authentication.
            protected_prefixes: List of path prefixes that require authentication.
            bypass_prefixes: List of path prefixes that bypass authentication even if matched by protected_prefixes.
        """
        super().__init__(app)
        self.api_key = api_key
        self.protected_prefixes = tuple(protected_prefixes or ["/api", "/mcp"])
        self.bypass_prefixes = tuple(bypass_prefixes or [])
        logger.info(
            f"Auth middleware initialized with protected={self.protected_prefixes}, bypass={self.bypass_prefixes}"
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and enforce authentication.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The response, or 401 if authentication fails.
        """
        path = request.url.path

        # Check for WebSocket upgrade - handled separately
        if path == "/ws":
            # WebSocket auth will be handled in the endpoint itself
            return await call_next(request)

        # Allow OPTIONS requests for CORS preflight checks
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check if path needs protection
        is_protected = path.startswith(self.protected_prefixes)
        if not is_protected:
            return await call_next(request)

        # Check if path is explicitly bypassed
        if path.startswith(self.bypass_prefixes):
            return await call_next(request)

        # Validate API key
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            logger.warning(f"Missing API key for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Missing X-API-Key header",
                },
            )

        if not secrets.compare_digest(api_key, self.api_key):
            logger.warning(f"Invalid API key for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "detail": "Invalid API key",
                },
            )

        # Authentication successful
        return await call_next(request)


def get_current_api_key(request: Request) -> str | None:
    """Extract and validate API key from request.

    This is a dependency injection helper for protected routes.

    Args:
        request: The incoming request.

    Returns:
        The validated API key or None if not present/valid.
    """
    return request.headers.get("X-API-Key")
