"""Plugin Manager service for Agent Pump.

This module provides the PluginManager service which handles discovery,
loading, and lifecycle management of plugins.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any

from agent_pump.events.bus import EventBus
from agent_pump.models.plugin import (
    HookContext,
    PluginConfig,
    PluginLoadError,
    PluginState,
    RegisteredHook,
)
from agent_pump.models.project import Project
from agent_pump.plugins.base import Plugin, PluginContext
from agent_pump.services.base import BaseService

logger = logging.getLogger(__name__)


class PluginManager(BaseService):
    """Service for managing Agent Pump plugins.

    The PluginManager handles plugin discovery, loading, initialization,
    and hook execution. It integrates with the workflow system to call
    plugin hooks at appropriate times.

    Plugins are loaded from the `.agent-pump/plugins/` directory within
    each project. Each plugin should be a Python module or package with
    a Plugin subclass.

    Example:
        plugin_manager = PluginManager(event_bus)
        plugin_manager.discover_plugins(Path("./my-project/.agent-pump/plugins"))
        plugin_manager.initialize_plugins(project)

    Attributes:
        plugins: Dictionary of loaded plugins by name
        hooks: Dictionary of registered hooks by phase
    """

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize the plugin manager.

        Args:
            event_bus: Event bus for plugin communication
        """
        super().__init__(event_bus)
        self._plugins: dict[str, PluginState] = {}
        self._hooks: dict[str | None, list[RegisteredHook]] = {}
        logger.debug("Initialized PluginManager")

    @property
    def plugins(self) -> dict[str, PluginState]:
        """Get all loaded plugins.

        Returns:
            Dictionary mapping plugin names to PluginState
        """
        return self._plugins.copy()

    @property
    def loaded_plugins(self) -> list[str]:
        """Get names of all loaded plugins.

        Returns:
            List of loaded plugin names
        """
        return list(self._plugins.keys())

    def discover_plugins(self, plugins_dir: Path) -> list[Path]:
        """Discover available plugins in a directory.

        Scans the plugins directory for Python modules and packages
        that might contain plugins.

        Args:
            plugins_dir: Path to the plugins directory

        Returns:
            List of paths to potential plugin modules
        """
        discovered: list[Path] = []

        if not plugins_dir.exists():
            logger.debug(f"Plugins directory does not exist: {plugins_dir}")
            return discovered

        if not plugins_dir.is_dir():
            logger.warning(f"Plugins path is not a directory: {plugins_dir}")
            return discovered

        for item in plugins_dir.iterdir():
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("_"):
                discovered.append(item)
                logger.debug(f"Discovered plugin module: {item.name}")
            elif item.is_dir() and (item / "__init__.py").exists():
                discovered.append(item)
                logger.debug(f"Discovered plugin package: {item.name}")

        logger.info(f"Discovered {len(discovered)} potential plugins in {plugins_dir}")
        return discovered

    def load_plugin(
        self,
        plugin_path: Path,
        config: dict[str, Any] | None = None,
    ) -> PluginState:
        """Load a plugin from a file or directory.

        Loads the plugin module, finds the Plugin subclass, and
        instantiates it.

        Args:
            plugin_path: Path to the plugin module or package
            config: Optional configuration dictionary for the plugin

        Returns:
            PluginState for the loaded plugin

        Raises:
            PluginLoadError: If the plugin cannot be loaded
        """
        if not plugin_path.exists():
            raise PluginLoadError(f"Plugin path does not exist: {plugin_path}")

        plugin_name = plugin_path.stem if plugin_path.is_file() else plugin_path.name

        try:
            # Load the module
            if plugin_path.is_file():
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            else:
                spec = importlib.util.spec_from_file_location(
                    plugin_name, plugin_path / "__init__.py"
                )

            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Cannot load spec for {plugin_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find Plugin subclass
            plugin_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, Plugin) and obj is not Plugin:
                    plugin_class = obj
                    break

            if plugin_class is None:
                raise PluginLoadError(f"No Plugin subclass found in {plugin_path}")

            # Instantiate plugin
            plugin = plugin_class(config)
            info = plugin.info

            # Parse config
            plugin_config = PluginConfig(**config) if config else PluginConfig()

            # Create state
            state = PluginState(
                info=info,
                instance=plugin,
                config=plugin_config,
                enabled=plugin_config.enabled,
            )

            self._plugins[info.name] = state
            logger.info(f"Loaded plugin: {info.name} v{info.version}")

            return state

        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin {plugin_path}: {e}") from e

    def unload_plugin(self, name: str) -> None:
        """Unload a plugin.

        Calls the plugin's shutdown method and removes it from
        the manager.

        Args:
            name: Name of the plugin to unload
        """
        if name not in self._plugins:
            logger.warning(f"Cannot unload unknown plugin: {name}")
            return

        state = self._plugins[name]

        try:
            state.instance.shutdown()
            logger.info(f"Shutdown plugin: {name}")
        except Exception as e:
            logger.error(f"Error shutting down plugin {name}: {e}")

        # Remove hooks
        for phase_hooks in self._hooks.values():
            phase_hooks[:] = [h for h in phase_hooks if h.plugin_name != name]

        del self._plugins[name]
        logger.info(f"Unloaded plugin: {name}")

    def initialize_plugins(
        self,
        project: Project,
        plugins_dir: Path | None = None,
    ) -> None:
        """Initialize all plugins for a project.

        Discovers, loads, and initializes all plugins for the given
        project. Sets up the plugin context with access to services.

        Args:
            project: The project to initialize plugins for
            plugins_dir: Optional override for plugins directory
        """
        if plugins_dir is None:
            plugins_dir = project.path / ".agent-pump" / "plugins"

        # Discover and load plugins
        discovered = self.discover_plugins(plugins_dir)

        for plugin_path in discovered:
            try:
                # Load plugin config if available
                config = self._load_plugin_config(plugin_path)

                # Load the plugin
                state = self.load_plugin(plugin_path, config)

                if not state.enabled:
                    logger.info(f"Skipping disabled plugin: {state.info.name}")
                    continue

                # Initialize with context
                context = PluginContext(
                    event_bus=self.event_bus,
                    project_path=project.path,
                    config_path=plugin_path.parent if plugin_path.is_file() else plugin_path,
                )
                state.instance.initialize(context)

                # Register hooks
                self._register_plugin_hooks(state, project)

            except PluginLoadError as e:
                logger.error(f"Failed to load plugin {plugin_path}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error loading plugin {plugin_path}: {e}")

        logger.info(f"Initialized {len(self._plugins)} plugins for {project.name}")

    def _load_plugin_config(self, plugin_path: Path) -> dict[str, Any]:
        """Load plugin configuration from config.yml file.

        Args:
            plugin_path: Path to the plugin module or package

        Returns:
            Configuration dictionary
        """
        import yaml

        if plugin_path.is_file():
            config_path = plugin_path.parent / "config.yml"
        else:
            config_path = plugin_path / "config.yml"

        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load plugin config from {config_path}: {e}")

        return {}

    def _register_plugin_hooks(self, state: PluginState, project: Project) -> None:
        """Register hooks for a loaded plugin.

        Inspects the plugin for hook methods and registers them.

        Args:
            state: PluginState containing the plugin instance
            project: The project context
        """
        plugin = state.instance
        plugin_name = state.info.name
        priority = state.config.priority

        # Register phase enter hook if implemented
        if hasattr(plugin, "on_phase_enter") and callable(plugin.on_phase_enter):
            hook = RegisteredHook(
                plugin_name=plugin_name,
                phase=None,  # All phases
                callback=plugin.on_phase_enter,
                priority=priority,
            )
            self._register_hook(hook)
            logger.debug(f"Registered phase_enter hook for {plugin_name}")

        # Register phase exit hook
        if hasattr(plugin, "on_phase_exit") and callable(plugin.on_phase_exit):
            hook = RegisteredHook(
                plugin_name=plugin_name,
                phase=None,
                callback=plugin.on_phase_exit,
                priority=priority,
            )
            self._register_hook(hook)
            logger.debug(f"Registered phase_exit hook for {plugin_name}")

        # Register verification hooks
        if hasattr(plugin, "on_verification_start"):
            hook = RegisteredHook(
                plugin_name=plugin_name,
                phase="verifying",
                callback=plugin.on_verification_start,
                priority=priority,
            )
            self._register_hook(hook)
            logger.debug(f"Registered verification_start hook for {plugin_name}")

        if hasattr(plugin, "on_verification_complete"):
            hook = RegisteredHook(
                plugin_name=plugin_name,
                phase="verifying",
                callback=plugin.on_verification_complete,
                priority=priority,
            )
            self._register_hook(hook)
            logger.debug(f"Registered verification_complete hook for {plugin_name}")

    def _register_hook(self, hook: RegisteredHook) -> None:
        """Register a hook for execution.

        Args:
            hook: RegisteredHook to register
        """
        phase_key = hook.phase
        if phase_key not in self._hooks:
            self._hooks[phase_key] = []

        self._hooks[phase_key].append(hook)
        # Sort by priority (lower first)
        self._hooks[phase_key].sort(key=lambda h: h.priority)

    async def execute_phase_hooks(
        self,
        phase: str,
        context: HookContext,
        hook_type: str,
    ) -> None:
        """Execute hooks for a phase.

        Args:
            phase: Current phase name
            context: HookContext with project information
            hook_type: Type of hook ('enter' or 'exit')
        """
        # Get global hooks (all phases) and phase-specific hooks
        hooks_to_run: list[RegisteredHook] = []

        if None in self._hooks:
            hooks_to_run.extend(self._hooks[None])

        if phase in self._hooks:
            hooks_to_run.extend(self._hooks[phase])

        # Sort by priority
        hooks_to_run.sort(key=lambda h: h.priority)

        for hook in hooks_to_run:
            try:
                # Check if this hook should run for this phase type
                plugin = self._plugins.get(hook.plugin_name)
                if not plugin or not plugin.enabled:
                    continue

                # Call the appropriate method on the plugin
                if hook_type == "enter":
                    if hook.phase is None or hook.phase == phase:
                        result = hook.callback(context)
                        if hasattr(result, "__await__"):
                            await result
                elif hook_type == "exit":
                    if hook.phase is None or hook.phase == phase:
                        result = hook.callback(context)
                        if hasattr(result, "__await__"):
                            await result

                logger.debug(f"Executed {hook_type} hook for {hook.plugin_name}")

            except Exception as e:
                logger.error(
                    f"Hook {hook_type} failed for plugin {hook.plugin_name}: {e}",
                    exc_info=True,
                )
                # Continue with other hooks - don't let one plugin crash others

    def get_custom_verification_steps(self) -> list[dict[str, Any]]:
        """Get all custom verification steps from plugins.

        Returns:
            List of custom verification step definitions
        """
        steps: list[dict[str, Any]] = []

        for state in self._plugins.values():
            if not state.enabled:
                continue

            try:
                plugin_steps = state.instance.get_custom_verification_steps()
                if plugin_steps:
                    steps.extend(plugin_steps)
                    logger.debug(
                        f"Added {len(plugin_steps)} verification steps from {state.info.name}"
                    )
            except Exception as e:
                logger.error(f"Failed to get verification steps from {state.info.name}: {e}")

        return steps

    def shutdown_all(self) -> None:
        """Shutdown all loaded plugins.

        Calls shutdown on all plugins and clears the registry.
        """
        for name, state in list(self._plugins.items()):
            try:
                state.instance.shutdown()
                logger.info(f"Shutdown plugin: {name}")
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")

        self._plugins.clear()
        self._hooks.clear()
        logger.info("All plugins shutdown")
