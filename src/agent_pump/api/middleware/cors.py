"""CORS middleware configuration for local development."""

from fastapi.middleware.cors import CORSMiddleware

# Default allowed origins for local development
DEFAULT_ORIGINS = [
    "http://localhost",
    "http://localhost:3000",  # Common React dev server
    "http://localhost:5173",  # Vite dev server
    "http://localhost:8000",  # FastAPI dev server
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]


def create_cors_middleware(
    origins: list[str] | None = None,
) -> type[CORSMiddleware]:
    """Create CORS middleware with the specified configuration.

    Args:
        origins: List of allowed origins. If None, uses default local development origins.

    Returns:
        Configured CORSMiddleware class.
    """
    return CORSMiddleware


def get_cors_config(origins: list[str] | None = None) -> dict:
    """Get CORS middleware configuration dictionary.

    Args:
        origins: List of allowed origins. If None, uses default local development origins.

    Returns:
        Dictionary with CORS middleware kwargs.
    """
    allowed_origins = origins or DEFAULT_ORIGINS

    return {
        "allow_origins": allowed_origins,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-API-Key"],
        "allow_credentials": True,
        "expose_headers": ["X-Request-ID"],
        "max_age": 600,  # 10 minutes
    }


def get_cors_config_secure(api_key: str | None = None, origins: list[str] | None = None) -> dict:
    """Get CORS middleware configuration dictionary for production with security.

    Args:
        api_key: API key for authentication. If provided, adds stricter security.
        origins: List of allowed origins. If None, uses default local development origins.

    Returns:
        Dictionary with CORS middleware kwargs for production.
    """
    allowed_origins = origins or DEFAULT_ORIGINS

    config = {
        "allow_origins": allowed_origins,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-API-Key"],
        "allow_credentials": True,
        "expose_headers": ["X-Request-ID"],
        "max_age": 600,  # 10 minutes
    }

    # If API key is configured, add stricter security
    if api_key:
        config["allow_methods"] = ["GET", "POST", "OPTIONS"]  # Limit methods
        # Note: We allow X-API-Key as it is required for authentication
        # Note: We allow all configured origins to support development servers

    return config
