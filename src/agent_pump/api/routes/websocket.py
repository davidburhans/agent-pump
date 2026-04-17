"""WebSocket endpoint for real-time updates with collaborative mode support."""

import asyncio
import json
import logging
import secrets
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from starlette.websockets import WebSocketState

from agent_pump.models.activity import ActivityType
from agent_pump.services.activity_service import ActivityService
from agent_pump.services.collaboration_service import CollaborationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class ConnectionManager:
    """Manage WebSocket connections with room support for collaborative mode."""

    def __init__(
        self,
        collaboration_service: CollaborationService | None = None,
        activity_service: ActivityService | None = None,
    ) -> None:
        """Initialize the connection manager."""
        self.active_connections: dict[str, WebSocket] = {}
        self.user_sessions: dict[str, str] = {}
        self.rooms: dict[str, set[str]] = {}
        self.collaboration_service = collaboration_service
        self.activity_service = activity_service
        self._bridge_task: asyncio.Task | None = None

    def set_services(
        self,
        collaboration_service: CollaborationService,
        activity_service: ActivityService,
    ) -> None:
        """Set the collaboration and activity services."""
        self.collaboration_service = collaboration_service
        self.activity_service = activity_service

    def start_event_bridge(self, event_bus: Any) -> None:
        """Start the EventBus-to-WebSocket bridge task."""
        if self._bridge_task is not None:
            logger.warning("Event bridge task already running, stopping it first")
            self.stop_event_bridge()

        self._bridge_task = asyncio.create_task(self._event_bridge_loop(event_bus))
        logger.info("EventBus-to-WebSocket bridge started")

    def stop_event_bridge(self) -> None:
        """Stop the EventBus-to-WebSocket bridge task."""
        if self._bridge_task is not None:
            self._bridge_task.cancel()
            self._bridge_task = None
            logger.info("EventBus-to-WebSocket bridge stopped")

    async def _event_bridge_loop(self, event_bus: Any) -> None:
        """Async loop to process events from the EventBus and broadcast them."""
        from agent_pump.events.models import LogEntryEvent, WorkflowStateChangedEvent
        from agent_pump.api.schemas import LogEntryDTO

        try:
            async for event in event_bus.subscribe():
                try:
                    if isinstance(event, LogEntryEvent):
                        if event.project_path:
                            # Normalize path for matching room key
                            project_path_str = str(event.project_path.resolve())
                            dto = LogEntryDTO.from_internal(event)
                            await self.broadcast_to_room(
                                project_path_str,
                                {
                                    "type": "log_entry",
                                    **dto.model_dump(by_alias=True)
                                }
                            )
                    elif isinstance(event, WorkflowStateChangedEvent):
                        if event.project_path:
                            project_path_str = str(event.project_path.resolve())
                            await self.broadcast_to_room(
                                project_path_str,
                                {
                                    "type": "workflow_state",
                                    "projectPath": project_path_str,
                                    "project_path": project_path_str,
                                    "newState": event.new_state,
                                    "currentState": event.new_state,
                                    "new_state": event.new_state,
                                    "old_state": event.old_state,
                                    "timestamp": event.timestamp.isoformat()
                                }
                            )
                except Exception as e:
                    logger.error(f"Error in EventBus WebSocket bridge processing event: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"EventBus-to-WebSocket bridge crashed: {e}")

    async def connect(
        self,
        websocket: WebSocket,
        session_id: str,
        user_name: str | None = None,
        role: str = "viewer",
        project_path: str | None = None,
    ) -> dict[str, Any] | None:
        """Accept a new WebSocket connection and register user.

        Args:
            websocket: The WebSocket connection.
            session_id: Unique session identifier.
            user_name: Optional user name for collaborative mode.
            role: User role (viewer or controller).
            project_path: Optional project the user is viewing.

        Returns:
            User info dict if collaborative mode, None otherwise.
        """
        await websocket.accept()
        self.active_connections[session_id] = websocket

        user_info = None

        # Register with collaboration service if available
        if self.collaboration_service and user_name:
            try:
                user = await self.collaboration_service.join_session(
                    user_name=user_name,
                    role=role,
                    session_id=session_id,
                    project_path=project_path,
                )
                self.user_sessions[session_id] = str(user.id)
                user_info = {
                    "id": str(user.id),
                    "name": user.name,
                    "role": user.role.value,
                }

                # Log activity
                if self.activity_service:
                    await self.activity_service.log_activity(
                        user_id=user.id,
                        user_name=user.name,
                        action=ActivityType.USER_JOINED,
                        project_path=project_path,
                    )

            except ValueError as e:
                logger.warning(f"Failed to join collaborative session: {e}")
                # Still allow connection, but without collaborative features

        # Join room if project path specified
        if project_path:
            self.join_room(session_id, project_path)

        logger.info(
            f"WebSocket client connected (session: {session_id}). "
            f"Total connections: {len(self.active_connections)}"
        )

        return user_info

    def disconnect(self, session_id: str) -> None:
        """Remove a WebSocket connection and clean up."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]

        # Leave all rooms
        for room_name in list(self.rooms.keys()):
            self.leave_room(session_id, room_name)

        # Unregister from collaboration service
        if self.collaboration_service and session_id in self.user_sessions:
            user_id = self.user_sessions[session_id]
            from uuid import UUID

            try:
                asyncio.create_task(self.collaboration_service.leave_session(UUID(user_id)))
            except Exception as e:
                logger.warning(f"Failed to unregister collaboration session for {user_id}: {e}")
            del self.user_sessions[session_id]

        logger.info(
            f"WebSocket client disconnected (session: {session_id}). "
            f"Total connections: {len(self.active_connections)}"
        )

    def join_room(self, session_id: str, room_name: str) -> None:
        """Add a connection to a room."""
        if room_name not in self.rooms:
            self.rooms[room_name] = set()
        self.rooms[room_name].add(session_id)
        logger.debug(f"Session {session_id} joined room: {room_name}")

    def leave_room(self, session_id: str, room_name: str) -> None:
        """Remove a connection from a room."""
        if room_name in self.rooms:
            self.rooms[room_name].discard(session_id)
            if not self.rooms[room_name]:
                del self.rooms[room_name]

    async def send_message(self, session_id: str, message: dict[str, Any]) -> bool:
        """Send a message to a specific client."""
        if session_id not in self.active_connections:
            return False

        websocket = self.active_connections[session_id]
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json(message)
                return True
        except Exception as e:
            logger.debug(f"Failed to send message to {session_id}: {e}")
            self.disconnect(session_id)

        return False

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Broadcast a message to all connected clients."""
        disconnected = []

        for session_id, websocket in list(self.active_connections.items()):
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
            except Exception as e:
                logger.debug(f"Failed to send broadcast to {session_id}: {e}")
                disconnected.append(session_id)

        # Clean up disconnected clients
        for session_id in disconnected:
            self.disconnect(session_id)

    async def broadcast_to_room(
        self, room_name: str, message: dict[str, Any], exclude: str | None = None
    ) -> None:
        """Broadcast a message to all clients in a room."""
        if room_name not in self.rooms:
            return

        disconnected = []
        room_members = list(self.rooms[room_name])

        for session_id in room_members:
            if session_id == exclude:
                continue

            if session_id not in self.active_connections:
                disconnected.append(session_id)
                continue

            websocket = self.active_connections[session_id]
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
            except Exception:
                disconnected.append(session_id)

        # Clean up disconnected clients
        for session_id in disconnected:
            self.leave_room(session_id, room_name)
            if session_id in self.active_connections:
                self.disconnect(session_id)

    async def handle_message(self, session_id: str, message: dict[str, Any]) -> None:
        """Handle incoming collaborative messages."""
        if not self.collaboration_service:
            return

        msg_type = message.get("type")
        user_id = self.user_sessions.get(session_id)

        if not user_id:
            return

        from uuid import UUID

        user_uuid = UUID(user_id)
        user = self.collaboration_service.get_user(user_uuid)

        if not user:
            return

        # Check permissions
        if msg_type in ["inject_idea", "pause_workflow", "resume_workflow", "approve_gate"]:
            if not user.can_control():
                await self.send_message(
                    session_id,
                    {"type": "error", "message": "Insufficient permissions"},
                )
                return

        # Handle specific message types
        if msg_type == "inject_idea":
            await self._handle_inject_idea(session_id, user_uuid, user.name, message)
        elif msg_type == "pause_workflow":
            await self._handle_workflow_control(session_id, user_uuid, user.name, "pause", message)
        elif msg_type == "resume_workflow":
            await self._handle_workflow_control(session_id, user_uuid, user.name, "resume", message)
        elif msg_type == "join_project":
            await self._handle_join_project(session_id, user_uuid, message)
        elif msg_type == "heartbeat":
            await self._handle_heartbeat(session_id, user_uuid)

    async def _handle_inject_idea(
        self,
        session_id: str,
        user_id: Any,
        user_name: str,
        message: dict[str, Any],
    ) -> None:
        """Handle idea injection message."""
        idea = message.get("idea", "").strip()
        project_path = message.get("project_path")

        if not idea:
            await self.send_message(
                session_id, {"type": "error", "message": "Idea cannot be empty"}
            )
            return

        # Log activity
        if self.activity_service:
            await self.activity_service.log_activity(
                user_id=user_id,
                user_name=user_name,
                action=ActivityType.IDEA_INJECTED,
                project_path=project_path,
                details={"idea_preview": idea[:50]},
            )

        # Broadcast to room
        if project_path:
            await self.broadcast_to_room(
                project_path,
                {
                    "type": "idea_injected",
                    "user_name": user_name,
                    "idea_preview": idea[:50],
                    "timestamp": datetime.now().isoformat(),
                },
                exclude=session_id,
            )

        await self.send_message(session_id, {"type": "idea_confirmed", "idea_preview": idea[:50]})

    async def _handle_workflow_control(
        self,
        session_id: str,
        user_id: Any,
        user_name: str,
        action: str,
        message: dict[str, Any],
    ) -> None:
        """Handle workflow control messages."""
        project_path = message.get("project_path")
        activity_type = (
            ActivityType.WORKFLOW_PAUSED if action == "pause" else ActivityType.WORKFLOW_RESUMED
        )

        # Log activity
        if self.activity_service:
            await self.activity_service.log_activity(
                user_id=user_id,
                user_name=user_name,
                action=activity_type,
                project_path=project_path,
            )

        # Broadcast to room
        if project_path:
            await self.broadcast_to_room(
                project_path,
                {
                    "type": f"workflow_{action}d",
                    "user_name": user_name,
                    "timestamp": datetime.now().isoformat(),
                },
                exclude=session_id,
            )

        await self.send_message(
            session_id, {"type": "workflow_control_confirmed", "action": action}
        )

    async def _handle_join_project(
        self, session_id: str, user_id: Any, message: dict[str, Any]
    ) -> None:
        """Handle join project message."""
        old_project = None
        user = self.collaboration_service.get_user(user_id) if self.collaboration_service else None
        if user:
            old_project = user.project_path

        new_project = message.get("project_path")

        # Update user's project
        if self.collaboration_service:
            self.collaboration_service.set_user_project(user_id, new_project)

        # Leave old room, join new room
        if old_project:
            self.leave_room(session_id, old_project)

            await self.broadcast_to_room(
                old_project,
                {
                    "type": "user_left_project",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                },
                exclude=session_id,
            )

        if new_project:
            self.join_room(session_id, new_project)

            await self.broadcast_to_room(
                new_project,
                {
                    "type": "user_joined_project",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                },
                exclude=session_id,
            )

        await self.send_message(
            session_id,
            {"type": "project_joined", "project_path": new_project},
        )

    async def _handle_heartbeat(self, session_id: str, user_id: Any) -> None:
        """Handle heartbeat message to keep user active."""
        if self.collaboration_service:
            self.collaboration_service.update_user_activity(user_id)

        await self.send_message(session_id, {"type": "heartbeat_ack"})


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time updates with collaborative mode support.

    Query Parameters:
        - name: User name (optional, enables collaborative mode)
        - role: User role - "viewer" or "controller" (default: "viewer")
        - project: Project path being viewed (optional)
    """
    import uuid

    # Generate unique session ID
    session_id = str(uuid.uuid4())

    # Get query parameters (if any)
    query_params = dict(websocket.query_params)
    user_name = query_params.get("name")
    role = query_params.get("role", "viewer")
    project_path = query_params.get("project")

    # Enforce Authentication
    # Check if API key is configured in app state (set in server.py)
    configured_key = getattr(websocket.app.state, "api_key", None)
    if configured_key:
        # Check for key in headers or query params
        # Note: Browsers generally don't support custom headers for WebSocket
        request_key = websocket.headers.get("X-API-Key") or query_params.get("api_key")

        if not request_key or not secrets.compare_digest(request_key, configured_key):
            logger.warning(
                f"Unauthorized WebSocket connection attempt. Session: {session_id}, User: {user_name}"
            )
            # Close with Policy Violation code (1008)
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # Connect and register
    user_info = await manager.connect(
        websocket=websocket,
        session_id=session_id,
        user_name=user_name,
        role=role,
        project_path=project_path,
    )

    try:
        # Send initial connection confirmation
        welcome_msg: dict[str, Any] = {
            "type": "connected",
            "session_id": session_id,
            "message": "WebSocket connection established",
        }
        if user_info:
            welcome_msg["user"] = user_info
            welcome_msg["collaborative_mode"] = True

        await manager.send_message(session_id, welcome_msg)

        while True:
            # Receive messages
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message from {session_id}: {data}")

            try:
                message = json.loads(data)
                await manager.handle_message(session_id, message)
            except json.JSONDecodeError:
                # Echo non-JSON messages
                await manager.send_message(
                    session_id,
                    {"type": "echo", "received": data},
                )

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info(f"WebSocket client disconnected normally (session: {session_id})")
    except Exception as e:
        manager.disconnect(session_id)
        logger.error(f"WebSocket error (session: {session_id}): {e}")
