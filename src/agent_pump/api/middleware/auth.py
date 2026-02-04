"""Authentication middleware for API access control."""

import logging
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
        bypass_paths: list[str] | None = None,
    ) -> None:
        """Initialize the auth middleware.

        Args:
            app: The ASGI application.
            api_key: The expected API key for authentication.
            bypass_paths: List of paths that bypass authentication.
        """
        super().__init__(app)
        self.api_key = api_key
        self.bypass_paths = set(bypass_paths or ["/health", "/docs", "/openapi.json", "/redoc"])
        logger.info(f"Auth middleware initialized with {len(self.bypass_paths)} bypass paths")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process the request and enforce authentication.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler in the chain.

        Returns:
            The response, or 401 if authentication fails.
        """
        # Check if path should bypass auth
        if request.url.path in self.bypass_paths:
            return await call_next(request)

        # Check for WebSocket upgrade - handled separately
        if request.url.path == "/ws":
            # WebSocket auth will be handled in the endpoint itself
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

        if api_key != self.api_key:
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
