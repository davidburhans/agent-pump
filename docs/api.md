# Agent Pump HTTP API Documentation

This document describes the HTTP API and WebSocket interface provided by Agent Pump's web server.

## Overview

The Agent Pump HTTP server provides a RESTful API and WebSocket interface for programmatic access to the Agent Pump orchestration system. It enables:

- Remote monitoring of project status
- Real-time log streaming
- Third-party integrations
- Web dashboard functionality

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   HTTP Client   │     │  WebSocket Cli  │     │     TUI         │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    FastAPI Server       │
                    │  ┌───────────────────┐  │
                    │  │  /health (REST)   │  │
                    │  │  /ws (WebSocket)  │  │
                    │  │  /docs (OpenAPI)  │  │
                    │  └───────────────────┘  │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    Shared Services      │
                    │  (Project, Log, etc.)   │
                    └─────────────────────────┘
```

## Running the Server

### Command Line

```bash
# Start server on default port (8000)
agent-pump --web

# Start server on custom port
agent-pump --web --web-port 8080
```

### Standalone Mode

When using `--web`, the server runs without the TUI, allowing remote access and headless operation.

## API Endpoints

### Health Check

**Endpoint:** `GET /health`

**Authentication:** Optional (bypasses auth when configured)

**Description:** Returns the current status of the Agent Pump server.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-01-15T10:30:00.000000",
  "version": "0.1.0",
  "uptimeSeconds": 3600.5
}
```

**Fields:**
- `status` (string): Service status, always "ok" when healthy
- `timestamp` (string): Current server timestamp in ISO 8601 format
- `version` (string): Agent Pump version
- `uptimeSeconds` (number | null): Server uptime in seconds, null if startup incomplete

**Example:**
```bash
curl http://localhost:8000/health
```

---

### WebSocket Connection

**Endpoint:** `WS /ws`

**Authentication:** Required (if enabled via API key)

**Description:** Real-time bidirectional communication for live updates.

**Connection Flow:**

1. Client connects to `ws://localhost:8000/ws`
2. Server sends connection confirmation:
   ```json
   {
     "type": "connected",
     "message": "WebSocket connection established"
   }
   ```
3. Client can send messages (currently echoes back)
4. Server may broadcast updates (future implementation)

**Message Types:**

| Type | Direction | Description |
|------|-----------|-------------|
| `connected` | Server → Client | Connection established |
| `echo` | Server → Client | Echo of client message (testing) |
| `status_update` | Server → Client | Project status change (future) |
| `log_entry` | Server → Client | New log entry (future) |

**Example (JavaScript):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

ws.send('Hello Server');
```

---

### API Documentation

**Endpoints:**
- `GET /docs` - Swagger UI (debug mode only)
- `GET /redoc` - ReDoc documentation (debug mode only)
- `GET /openapi.json` - OpenAPI schema (debug mode only)

**Description:** Interactive API documentation generated automatically from FastAPI.

---

## Authentication

### API Key Authentication

When an API key is configured, protected endpoints require the `X-API-Key` header.

**Header Format:**
```
X-API-Key: your-api-key-here
```

**Bypassed Paths:**
The following paths bypass authentication (configurable):
- `/health` - Health check
- `/docs` - API documentation
- `/redoc` - Alternative documentation
- `/openapi.json` - OpenAPI schema

**Example:**
```bash
curl -H "X-API-Key: secret123" http://localhost:8000/protected-endpoint
```

### Configuration

API keys are configured when creating the server instance:

```python
from agent_pump.api.server import create_server

# With authentication
app = create_server(api_key="your-secret-key")

# Without authentication (default)
app = create_server(api_key=None)
```

---

## CORS Configuration

Cross-Origin Resource Sharing (CORS) is configured for local development by default.

### Default Allowed Origins

- `http://localhost`
- `http://localhost:3000` (React dev server)
- `http://localhost:5173` (Vite dev server)
- `http://localhost:8000`
- `http://127.0.0.1` and variants

### Allowed Methods

- GET
- POST
- PUT
- DELETE
- OPTIONS

### Allowed Headers

- Content-Type
- Authorization
- X-API-Key

### Configuration

Custom origins can be provided when creating the server:

```python
app = create_server(
    cors_origins=["https://myapp.example.com"]
)
```

---

## Error Handling

### HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Not found |
| 500 | Internal server error |

### Error Response Format

```json
{
  "error": "Unauthorized",
  "detail": "Missing X-API-Key header"
}
```

In debug mode, detailed error messages are included. In production, generic messages are returned for security.

---

## Server Configuration

### Factory Function

The `create_server()` function configures the FastAPI application:

```python
create_server(
    api_key: str | None = None,        # API key for auth (None = disabled)
    cors_origins: list[str] | None = None,  # Custom CORS origins
    debug: bool = False,              # Enable debug mode (docs, detailed errors)
) -> FastAPI
```

### Lifespan Management

The server uses FastAPI's lifespan context manager for startup/shutdown:

1. **Startup:**
   - Log server start
   - Initialize shared services
   - Record startup time

2. **Shutdown:**
   - Log server stop
   - Calculate and log uptime
   - Clean up resources

---

## Future Endpoints

The following endpoints are planned for future implementation:

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/projects | List all projects |
| GET | /api/projects/{id} | Get project details |
| POST | /api/projects/{id}/start | Start project workflow |
| POST | /api/projects/{id}/stop | Stop project workflow |
| GET | /api/projects/{id}/logs | Get project logs |
| GET | /api/workspaces | List workspaces |
| POST | /api/workspaces/{id}/switch | Switch workspace |

---

## Testing

### Running Tests

```bash
# Run API tests
uv run pytest tests/unit/api/ -v

# Run integration tests
uv run pytest tests/integration/test_server.py -v
```

### Test Coverage

The test suite covers:
- Health endpoint responses
- WebSocket connection handling
- CORS header presence
- Authentication middleware
- Server startup/shutdown

---

## Code Examples

### Python Client

```python
import requests
import websocket

# Health check
response = requests.get("http://localhost:8000/health")
print(response.json())

# WebSocket connection
def on_message(ws, message):
    print(f"Received: {message}")

ws = websocket.WebSocketApp(
    "ws://localhost:8000/ws",
    on_message=on_message,
    header=["X-API-Key: your-key"]
)
ws.run_forever()
```

### curl Examples

```bash
# Health check
curl http://localhost:8000/health

# With authentication
curl -H "X-API-Key: secret" http://localhost:8000/health

# WebSocket connection (using wscat)
npx wscat -c ws://localhost:8000/ws -H "X-API-Key: secret"
```

---

## Development Notes

### Architecture Decisions

1. **FastAPI**: Chosen for its async support, automatic OpenAPI generation, and modern Python features.

2. **DTOs (Data Transfer Objects)**: All API responses use DTOs defined in `agent_pump.api.schemas` to ensure consistent serialization.

3. **Middleware Stack**: 
   - CORS middleware runs first to handle preflight requests
   - Auth middleware runs second to protect routes
   - Both are configurable at server creation time

4. **WebSocket Manager**: A global connection manager handles multiple concurrent WebSocket connections for future broadcasting capabilities.

5. **Lifespan Events**: Used for proper resource initialization and cleanup, ensuring clean startup and shutdown.

### Security Considerations

- API keys should be strong and rotated regularly
- CORS origins should be restricted in production
- Debug mode should be disabled in production
- Input validation is handled by Pydantic models

---

## See Also

- [README.md](../README.md) - General project documentation
- [BEST_PRACTICES.md](../BEST_PRACTICES.md) - Engineering guidelines
- FastAPI documentation: https://fastapi.tiangolo.com/
