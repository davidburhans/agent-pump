"""FastAPI server with lifespan management."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agent_pump import __version__
from agent_pump.api.middleware.auth import AuthMiddleware
from agent_pump.api.middleware.cors import get_cors_config, get_cors_config_secure
from agent_pump.api.routes.health import router as health_router
from agent_pump.api.routes.metrics import router as metrics_router
from agent_pump.api.routes.projects import router as projects_router
from agent_pump.api.routes.webhooks import router as webhooks_router
from agent_pump.api.routes.websocket import router as websocket_router
from agent_pump.communication.callback_server import router as callback_router
from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.events.bus import EventBus
from agent_pump.models.app_state import AppState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[dict[str, Any], None]:
    """Manage application lifespan events."""
    # Startup
    logger.info("=" * 60)
    logger.info("Agent Pump HTTP Server Starting")
    logger.info(f"Version: {__version__}")
    logger.info(f"Startup time: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Initialize services
    try:
        from agent_pump.integrations.ci_watcher import CIWatcher
        from agent_pump.services.metrics_service import MetricsService
        from agent_pump.services.project_service import ProjectService
        from agent_pump.services.workspace_service import WorkspaceService

        logger.info("Initializing services...")
        app.state.app_state = AppState.load()
        app.state.event_bus = EventBus()
        app.state.workspace_service = WorkspaceService(app.state.event_bus, app.state.app_state)
        workspace = app.state.workspace_service.get_current_workspace()
        app.state.project_service = ProjectService(
            app.state.event_bus, workspace, app.state.app_state
        )

        # Initialize File Watcher
        from agent_pump.services.file_watcher_service import FileWatcherService

        app.state.file_watcher_service = FileWatcherService(
            app.state.event_bus, app.state.project_service, workspace
        )
        logger.info("File Watcher service initialized")

        # Initialize CI Watcher
        app.state.ci_watcher = CIWatcher(app.state.project_service)
        logger.info("CI Watcher service initialized")

        # Initialize metrics service
        app.state.metrics_service = MetricsService(app.state.event_bus, workspace.name)
        await app.state.metrics_service.start()
        logger.info("Metrics service initialized")

        # Load projects if enabled
        if getattr(app.state, "autoload_projects", True):
            for path_str in workspace.projects:
                await app.state.project_service.add_project(Path(path_str))

        app.state.startup_time = datetime.now()

        # Initialize MCP Server
        try:
            mcp_server = AgentPumpMCPServer(app.state)
            app.state.mcp_server = mcp_server
            # Mount SSE app
            app.mount("/mcp", mcp_server.sse_app)
            logger.info("MCP Server initialized and mounted at /mcp")
        except Exception as e:
            logger.error(f"Failed to initialize MCP Server: {e}")

        logger.info("Services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

    yield {"startup_time": app.state.startup_time}

    # Shutdown
    if hasattr(app.state, "mcp_server"):
        try:
            await app.state.mcp_server.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down MCP Server: {e}")

    logger.info("=" * 60)
    logger.info("Agent Pump HTTP Server Shutting Down")
    logger.info(f"Shutdown time: {datetime.now().isoformat()}")
    uptime = datetime.now() - app.state.startup_time
    logger.info(f"Uptime: {uptime}")
    logger.info("=" * 60)


def create_server(
    *,
    api_key: str | None = None,
    cors_origins: list[str] | None = None,
    debug: bool = False,
    autoload_projects: bool = True,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        api_key: Optional API key for authentication. If None, auth is disabled.
        cors_origins: List of allowed CORS origins. Defaults to localhost.
        debug: Enable debug mode for detailed error responses.
        autoload_projects: Whether to automatically load projects from workspace.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="Agent Pump API",
        description="HTTP API and WebSocket interface for Agent Pump",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if debug else None,
        redoc_url="/redoc" if debug else None,
        openapi_url="/openapi.json" if debug else None,
    )
    app.state.autoload_projects = autoload_projects

    # Add CORS middleware
    if api_key:
        logger.info("Authentication middleware enabled - using secure CORS")
        cors_config = get_cors_config_secure(api_key=api_key, origins=cors_origins)
    else:
        logger.info("Authentication middleware disabled - using default CORS")
        cors_config = get_cors_config(origins=cors_origins)
    app.add_middleware(CORSMiddleware, **cors_config)

    # Add authentication middleware if API key is configured
    if api_key:
        logger.info("Authentication middleware enabled")
        app.add_middleware(AuthMiddleware, api_key=api_key)
    else:
        logger.info("Authentication middleware disabled (no API key configured)")

    # Include routers
    app.include_router(health_router)
    app.include_router(projects_router, prefix="/api")
    app.include_router(metrics_router, prefix="/api")
    app.include_router(websocket_router)
    app.include_router(callback_router, prefix="/api")
    app.include_router(webhooks_router, prefix="/api")

    # Static files (SPA)
    # Determine static path relative to this file
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/assets", StaticFiles(directory=static_path / "assets"), name="assets")

        # Catch-all for SPA (must be last)
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # If path starts with /api or /ws, let it 404 naturally if not matched above
            if full_path.startswith("api") or full_path.startswith("ws"):
                return JSONResponse(status_code=404, content={"error": "Not Found"})

            # Serve index.html
            return FileResponse(static_path / "index.html")
    else:
        logger.warning(f"Static files directory not found: {static_path}")

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unhandled exceptions."""
        logger.exception(f"Unhandled exception in {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if debug else "An unexpected error occurred",
            },
        )

    logger.info(f"FastAPI application created (debug={debug})")
    return app


# Default app instance for direct import
app = create_server()
