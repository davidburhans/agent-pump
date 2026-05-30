import json
import logging
import secrets
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from agent_pump.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["chat"])

@router.websocket("/projects/{project_path:path}/chat")
async def chat_websocket_endpoint(websocket: WebSocket, project_path: str) -> None:
    """WebSocket endpoint for chat streaming."""
    await websocket.accept()

    # Enforce Auth
    configured_key = getattr(websocket.app.state, "api_key", None)
    if configured_key:
        query_params = dict(websocket.query_params)
        request_key = websocket.headers.get("X-API-Key") or query_params.get("api_key")
        if not request_key or not secrets.compare_digest(request_key, configured_key):
            logger.warning("Unauthorized WebSocket connection attempt to chat.")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    event_bus = getattr(websocket.app.state, "event_bus", None)
    if not event_bus:
        await websocket.send_json({"type": "error", "message": "Event bus not available"})
        await websocket.close()
        return

    chat_service = ChatService(event_bus)
    project_path_obj = Path(project_path)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                query = message.get("query", "")
                history = message.get("history", [])

                if not query:
                    continue

                await websocket.send_json({"type": "start"})

                async for chunk in chat_service.chat_stream(
                    query=query,
                    project_path=project_path_obj,
                    history=history
                ):
                    await websocket.send_json({"type": "chunk", "text": chunk})

                await websocket.send_json({"type": "end"})

            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})

    except WebSocketDisconnect:
        logger.info("Chat WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Chat WS error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
