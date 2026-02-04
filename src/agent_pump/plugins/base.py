"""Plugin base class and interfaces for Agent Pump.

This module defines the base Plugin class and hook interfaces that
plugins must implement to extend Agent Pump functionality.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_pump.events.bus import EventBus
    from agent_pump.models.plugin import HookContext, PluginInfo


class PluginContext:
    """Context provided to plugins during initialization.

    This gives plugins access to the core services they need to
    interact with Agent Pump.

    Attributes:
        event_bus: Event bus for publishing/subscribing to events
        project_path: Path to the project (may be None for global plugins)
        config_path: Path to plugin configuration directory
    """

    def __init__(
        self,
        event_bus: EventBus,
        project_path: Path | None,
        config_path: Path,
    ) -> None:
        self.event_bus = event_bus
        self.project_path = project_path
        self.config_path = config_path


class Plugin(ABC):
    """Base class for all Agent Pump plugins.

    All plugins must inherit from this class and implement the required
    methods. Plugins can optionally implement hooks for workflow events.

    Example:
        class MyPlugin(Plugin):
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(
                    name="my-plugin",
                    version="1.0.0",
                    description="My custom plugin"
                )

            def initialize(self, context: PluginContext) -> None:
                # Setup code here
                pass

            def shutdown(self) -> None:
                # Cleanup code here
                pass

    Attributes:
        config: Plugin configuration dictionary
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the plugin.

        Args:
            config: Plugin configuration dictionary from config file
        """
        self.config = config or {}
        self._context: PluginContext | None = None

    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Return plugin metadata.

        This property must be implemented by all plugins to provide
        basic information about the plugin.

        Returns:
            PluginInfo with name, version, description, etc.
        """
        ...

    def initialize(self, context: PluginContext) -> None:
        """Initialize the plugin with context.

        Called once when the plugin is loaded. Use this to set up
        event subscriptions, load resources, etc.

        Args:
            context: PluginContext with access to core services
        """
        self._context = context

    def shutdown(self) -> None:
        """Shutdown the plugin.

        Called when the plugin is being unloaded. Use this to clean up
        resources, unsubscribe from events, etc.
        """
        pass

    def on_phase_enter(self, context: HookContext) -> None:
        """Called when entering a workflow phase.

        Override this method to execute code before a phase runs.
        The phase is available in context.phase.

        Args:
            context: HookContext with project and phase information
        """
        pass

    def on_phase_exit(self, context: HookContext) -> None:
        """Called when exiting a workflow phase.

        Override this method to execute code after a phase completes.
        Check context.data.get('success') for phase result.

        Args:
            context: HookContext with project and phase information
        """
        pass

    def on_verification_start(self, context: HookContext) -> None:
        """Called before verification commands run.

        Override this method to perform custom actions before
        verification or to add custom verification steps.

        Args:
            context: HookContext with project information
        """
        pass

    def on_verification_complete(self, context: HookContext) -> None:
        """Called after verification commands complete.

        Override this method to perform custom actions after
        verification completes.

        Args:
            context: HookContext with project and results information
        """
        pass

    def get_custom_verification_steps(self) -> list[dict[str, Any]]:
        """Return custom verification steps to add.

        Override this method to provide custom verification commands
        that will be run alongside standard verification.

        Returns:
            List of verification step dictionaries with keys:
            - name: Step name
            - command: Command to execute
            - required: Whether step is required (default True)
        """
        return []


class WorkflowHooks:
    """Protocol for workflow hook implementations.

    This class defines the interface for plugins that want to hook
    into workflow lifecycle events. It can be used standalone or
    as a mixin with Plugin.
    """

    async def on_phase_enter(self, phase: str, context: HookContext) -> None:
        """Async version of on_phase_enter for async plugins.

        Args:
            phase: Name of the phase being entered
            context: HookContext with project information
        """
        pass

    async def on_phase_exit(self, phase: str, success: bool, context: HookContext) -> None:
        """Async version of on_phase_exit for async plugins.

        Args:
            phase: Name of the phase being exited
            success: Whether the phase completed successfully
            context: HookContext with project information
        """
        pass


class VerificationHooks:
    """Protocol for verification hook implementations.

    This class defines the interface for plugins that want to add
    custom verification steps or hook into verification events.
    """

    async def on_verification_start(self, context: HookContext) -> None:
        """Called before verification starts.

        Args:
            context: HookContext with project information
        """
        pass

    async def on_verification_complete(
        self,
        context: HookContext,
        results: list[dict[str, Any]],
    ) -> None:
        """Called after verification completes.

        Args:
            context: HookContext with project information
            results: List of verification step results
        """
        pass

    def get_verification_steps(self) -> list[dict[str, Any]]:
        """Return custom verification steps.

        Returns:
            List of verification step definitions
        """
        return []
