"""Workspace and configuration management service."""

import logging
from pathlib import Path

from agent_pump.events.bus import EventBus
from agent_pump.events.models import ConfigUpdatedEvent, WorkspaceSwitchedEvent
from agent_pump.models.app_state import AppState
from agent_pump.models.workspace import (
    GlobalPromptSettings,
    PhaseBackends,
    PromptCustomization,
    Workspace,
)
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


class WorkspaceService(BaseService):
    """Service for managing workspace and configuration."""

    def __init__(self, event_bus: EventBus, app_state: AppState) -> None:
        """
        Initialize the workspace service.

        Args:
            event_bus: The event bus.
            app_state: The global app state.
        """
        super().__init__(event_bus)
        self.app_state = app_state
        self._workspace: Workspace | None = None

    def get_current_workspace(self) -> Workspace:
        """
        Get the current workspace. Initializes it if necessary.

        Returns:
             The current Workspace object.
        """
        if self._workspace is None:
            # Logic to load workspace based on app_state or creating default
            # For now, we reuse the logic from AppState.load() used in app.py
            # But app.py loads AppState, then loads Workspace.
            # Here we assume caller injects AppState and we load workspace.

            # Since Workspace.load takes a path, we need to know that path.
            # AppState stores recent_workspaces? Or maybe we just use a default location?
            # app.py L156: self.workspace = Workspace.load(Path.home() / ".agent-pump" / "workspace.json")
            # We should probably standardize this location or allow injection.
            # For this service, let's assume valid default if not set.
            # Use path from app_state if available, otherwise default
            workspace_path = self.app_state.current_workspace
            # If app_state doesn't have it (unlikely if properly initialized), fallback
            if not workspace_path:
                workspace_path = Path.home() / ".agent-pump" / "workspace.json"

            self._workspace = Workspace.load(workspace_path)

        return self._workspace

    # Allow injection for dependency injection / testing
    def set_current_workspace(self, workspace: Workspace) -> None:
        self._workspace = workspace

    async def switch_workspace(self, name: str) -> Workspace:
        """
        Switch to a different workspace (placeholder logic as multiple workspaces support is minimal).

        Args:
            name: Name or path of the workspace.
        """
        # Placeholder implementation
        logger.info(f"Switching to workspace: {name}")
        await self.event_bus.publish(
            WorkspaceSwitchedEvent(old_workspace="default", new_workspace=name)
        )
        return self.get_current_workspace()

    async def update_backend_config(self, path: Path | None, config: PhaseBackends) -> None:
        """
        Update backend configuration.

        Args:
            path: Project path (None for global defaults).
            config: The new backend configuration.
        """
        workspace = self.get_current_workspace()
        if path:
            path = path.resolve()
            project_config = workspace.get_project_config(path)
            if project_config:
                project_config.phase_backends = config
                workspace.save()
                logger.info(f"Updated backend config for project: {path}")
                await self.event_bus.publish(
                    ConfigUpdatedEvent(project_path=path, config_type="backend")
                )
        else:
            workspace.default_phase_backends = config
            workspace.save()
            logger.info("Updated default backend config")
            await self.event_bus.publish(
                ConfigUpdatedEvent(project_path=None, config_type="backend")
            )

    async def update_prompt_config(self, path: Path, config: PromptCustomization) -> None:
        """
        Update prompt customization for a project.

        Args:
            path: Project path.
            config: The new prompt customization.
        """
        workspace = self.get_current_workspace()
        path = path.resolve()
        project_config = workspace.get_project_config(path)
        if project_config:
            project_config.prompt_customization = config
            workspace.save()
            logger.info(f"Updated prompt config for project: {path}")
            await self.event_bus.publish(
                ConfigUpdatedEvent(project_path=path, config_type="prompt")
            )

    async def update_global_prompts(self, settings: GlobalPromptSettings) -> None:
        """
        Update global prompt settings.

        Args:
            settings: The new global prompt settings.
        """
        workspace = self.get_current_workspace()
        workspace.global_prompt_settings = settings
        workspace.save()
        logger.info("Updated global prompt settings")
        await self.event_bus.publish(
            ConfigUpdatedEvent(project_path=None, config_type="global_prompt")
        )
