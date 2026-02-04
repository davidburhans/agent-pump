"""Tests for the Plugin Manager service."""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent_pump.events.bus import EventBus
from agent_pump.models.plugin import (
    HookContext,
    PluginConfig,
    PluginInfo,
    PluginLoadError,
    PluginState,
)
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.plugins.base import Plugin, PluginContext
from agent_pump.services.plugin_manager import PluginManager


# Example plugin classes for testing
class TestPlugin(Plugin):
    """Simple test plugin."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
        )

    def initialize(self, context: PluginContext) -> None:
        self.initialized = True
        self.context = context

    def shutdown(self) -> None:
        self.shut_down = True

    def on_phase_enter(self, context: HookContext) -> None:
        context.data["entered"] = True

    def on_phase_exit(self, context: HookContext) -> None:
        context.data["exited"] = True


class AsyncTestPlugin(Plugin):
    """Test plugin with async hooks."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="async-test-plugin",
            version="1.0.0",
            description="Async test plugin",
        )

    async def on_phase_enter(self, context: HookContext) -> None:
        await asyncio.sleep(0.01)
        context.data["async_entered"] = True

    async def on_phase_exit(self, context: HookContext) -> None:
        await asyncio.sleep(0.01)
        context.data["async_exited"] = True


class VerificationPlugin(Plugin):
    """Test plugin providing custom verification steps."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="verification-plugin",
            version="1.0.0",
            description="Provides custom verification",
        )

    def get_custom_verification_steps(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "custom-check",
                "command": "echo 'Custom verification'",
                "required": True,
            }
        ]


@pytest.fixture
def event_bus():
    """Create an event bus for testing."""
    return EventBus()


@pytest.fixture
def plugin_manager(event_bus):
    """Create a plugin manager for testing."""
    return PluginManager(event_bus)


@pytest.fixture
def temp_project(tmp_path) -> Project:
    """Create a temporary project for testing."""
    project = Project(
        path=tmp_path,
        name="test-project",
        status=ProjectStatus.IDLE,
    )
    return project


class TestPluginManagerInitialization:
    """Test plugin manager initialization."""

    def test_init(self, event_bus):
        """Test that PluginManager initializes correctly."""
        manager = PluginManager(event_bus)

        assert manager.event_bus == event_bus
        assert manager.loaded_plugins == []
        assert manager.plugins == {}

    def test_init_without_event_bus(self):
        """Test that PluginManager handles missing event bus gracefully."""
        # PluginManager accepts None event bus but will fail when trying to use it
        # This is acceptable behavior - it's a programming error not a runtime error
        manager = PluginManager(None)  # type: ignore
        assert manager.event_bus is None


class TestPluginDiscovery:
    """Test plugin discovery."""

    def test_discover_plugins_empty_dir(self, plugin_manager, tmp_path):
        """Test discovery with empty directory."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        discovered = plugin_manager.discover_plugins(plugins_dir)

        assert discovered == []

    def test_discover_plugins_no_dir(self, plugin_manager, tmp_path):
        """Test discovery with non-existent directory."""
        plugins_dir = tmp_path / "nonexistent"

        discovered = plugin_manager.discover_plugins(plugins_dir)

        assert discovered == []

    def test_discover_plugins_single_file(self, plugin_manager, tmp_path):
        """Test discovery of single plugin file."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_file = plugins_dir / "my_plugin.py"
        plugin_file.write_text("# Test plugin")

        discovered = plugin_manager.discover_plugins(plugins_dir)

        assert len(discovered) == 1
        assert discovered[0] == plugin_file

    def test_discover_plugins_package(self, plugin_manager, tmp_path):
        """Test discovery of plugin package."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        pkg_dir = plugins_dir / "my_package"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("# Test package")

        discovered = plugin_manager.discover_plugins(plugins_dir)

        assert len(discovered) == 1
        assert discovered[0] == pkg_dir

    def test_discover_plugins_ignores_private(self, plugin_manager, tmp_path):
        """Test that private files are ignored."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "_private.py").write_text("# Private")
        (plugins_dir / "__init__.py").write_text("# Init")
        (plugins_dir / "public.py").write_text("# Public")

        discovered = plugin_manager.discover_plugins(plugins_dir)

        assert len(discovered) == 1
        assert discovered[0].name == "public.py"

    def test_discover_plugins_ignores_non_python(self, plugin_manager, tmp_path):
        """Test that non-Python files are ignored."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "readme.md").write_text("# Readme")
        (plugins_dir / "plugin.py").write_text("# Plugin")
        (plugins_dir / "config.yml").write_text("config: value")

        discovered = plugin_manager.discover_plugins(plugins_dir)

        assert len(discovered) == 1
        assert discovered[0].name == "plugin.py"


class TestPluginLoading:
    """Test plugin loading."""

    def test_load_plugin_from_class(self, plugin_manager):
        """Test loading a plugin from a class."""
        # Create a temporary plugin file
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("""
from agent_pump.plugins.base import Plugin
from agent_pump.models.plugin import PluginInfo

class TestPlugin(Plugin):
    @property
    def info(self):
        return PluginInfo(name="loaded-plugin", version="1.0.0")
""")
            temp_path = Path(f.name)

        try:
            state = plugin_manager.load_plugin(temp_path)

            assert state.info.name == "loaded-plugin"
            assert state.info.version == "1.0.0"
            assert "loaded-plugin" in plugin_manager.loaded_plugins
        finally:
            temp_path.unlink()

    def test_load_plugin_nonexistent(self, plugin_manager):
        """Test loading a non-existent plugin."""
        with pytest.raises(PluginLoadError):
            plugin_manager.load_plugin(Path("/nonexistent/plugin.py"))

    def test_load_plugin_no_subclass(self, plugin_manager, tmp_path):
        """Test loading a file without Plugin subclass."""
        plugin_file = tmp_path / "no_plugin.py"
        plugin_file.write_text("# No Plugin subclass here")

        with pytest.raises(PluginLoadError) as exc_info:
            plugin_manager.load_plugin(plugin_file)

        assert "No Plugin subclass found" in str(exc_info.value)

    def test_load_plugin_with_config(self, plugin_manager, tmp_path):
        """Test loading a plugin with configuration."""
        # Create plugin file
        plugin_file = tmp_path / "configured.py"
        plugin_file.write_text("""
from agent_pump.plugins.base import Plugin
from agent_pump.models.plugin import PluginInfo

class ConfiguredPlugin(Plugin):
    @property
    def info(self):
        return PluginInfo(name="configured-plugin", version="1.0.0")

    def initialize(self, context):
        self.config_value = self.config.get("custom_key", "default")
""")

        config = {"custom_key": "custom_value"}
        state = plugin_manager.load_plugin(plugin_file, config)

        assert state.config.enabled is True
        # Config should be passed to plugin instance
        assert state.instance.config == config


class TestPluginLifecycle:
    """Test plugin lifecycle (initialize/shutdown)."""

    @pytest.mark.asyncio
    async def test_initialize_plugins(self, plugin_manager, temp_project, tmp_path):
        """Test initializing plugins for a project."""
        plugins_dir = tmp_path / ".agent-pump" / "plugins"
        plugins_dir.mkdir(parents=True)

        # Create a test plugin
        plugin_file = plugins_dir / "lifecycle.py"
        plugin_file.write_text("""
from agent_pump.plugins.base import Plugin, PluginContext
from agent_pump.models.plugin import PluginInfo, HookContext

class LifecyclePlugin(Plugin):
    initialized = False
    
    @property
    def info(self):
        return PluginInfo(name="lifecycle-plugin", version="1.0.0")
    
    def initialize(self, context: PluginContext):
        self.initialized = True
        self.ctx = context
""")

        # Create project in temp dir
        temp_project.path = tmp_path

        plugin_manager.initialize_plugins(temp_project, plugins_dir)

        assert "lifecycle-plugin" in plugin_manager.loaded_plugins
        plugin_state = plugin_manager.plugins["lifecycle-plugin"]
        assert plugin_state.instance.initialized is True
        assert plugin_state.instance.ctx is not None

    def test_unload_plugin(self, plugin_manager, tmp_path):
        """Test unloading a plugin."""
        # Create and load a plugin
        plugin_file = tmp_path / "unload.py"
        plugin_file.write_text("""
from agent_pump.plugins.base import Plugin
from agent_pump.models.plugin import PluginInfo

class UnloadPlugin(Plugin):
    @property
    def info(self):
        return PluginInfo(name="unload-plugin", version="1.0.0")
    
    def shutdown(self):
        self.shut_down = True
""")

        state = plugin_manager.load_plugin(plugin_file)
        plugin_manager.unload_plugin("unload-plugin")

        assert "unload-plugin" not in plugin_manager.loaded_plugins

    def test_shutdown_all(self, plugin_manager, tmp_path):
        """Test shutting down all plugins."""
        # Create multiple plugins
        for i in range(3):
            plugin_file = tmp_path / f"plugin{i}.py"
            plugin_file.write_text(f"""
from agent_pump.plugins.base import Plugin
from agent_pump.models.plugin import PluginInfo

class Plugin{i}(Plugin):
    @property
    def info(self):
        return PluginInfo(name="plugin-{i}", version="1.0.0")
""")
            plugin_manager.load_plugin(plugin_file)

        plugin_manager.shutdown_all()

        assert plugin_manager.loaded_plugins == []


class TestPluginHooks:
    """Test plugin hook execution."""

    @pytest.mark.asyncio
    async def test_execute_phase_hooks_enter(self, plugin_manager, temp_project):
        """Test executing enter hooks."""
        plugin = TestPlugin()
        state = PluginState(
            info=plugin.info,
            instance=plugin,
            config=PluginConfig(),
            enabled=True,
            hooks=[],
        )
        plugin_manager._plugins["test-plugin"] = state
        # Register hooks properly
        plugin_manager._register_plugin_hooks(state, temp_project)

        context = HookContext(
            project=temp_project,
            phase="planning",
            feature="test-feature",
        )

        await plugin_manager.execute_phase_hooks("planning", context, "enter")

        assert context.data.get("entered") is True

    @pytest.mark.asyncio
    async def test_execute_phase_hooks_exit(self, plugin_manager, temp_project):
        """Test executing exit hooks."""
        plugin = TestPlugin()
        state = PluginState(
            info=plugin.info,
            instance=plugin,
            config=PluginConfig(),
            enabled=True,
            hooks=[],
        )
        plugin_manager._plugins["test-plugin"] = state
        # Register hooks properly
        plugin_manager._register_plugin_hooks(state, temp_project)

        context = HookContext(
            project=temp_project,
            phase="planning",
            feature="test-feature",
        )

        await plugin_manager.execute_phase_hooks("planning", context, "exit")

        assert context.data.get("exited") is True

    @pytest.mark.asyncio
    async def test_execute_async_hooks(self, plugin_manager, temp_project):
        """Test executing async hooks."""
        plugin = AsyncTestPlugin()
        state = PluginState(
            info=plugin.info,
            instance=plugin,
            config=PluginConfig(),
            enabled=True,
            hooks=[],
        )
        # Use the plugin's actual name as the key
        plugin_manager._plugins[plugin.info.name] = state
        # Register hooks properly
        plugin_manager._register_plugin_hooks(state, temp_project)

        context = HookContext(
            project=temp_project,
            phase="implementing",
            feature="test",
        )

        await plugin_manager.execute_phase_hooks("implementing", context, "enter")

        assert context.data.get("async_entered") is True

    @pytest.mark.asyncio
    async def test_disabled_plugin_not_executed(self, plugin_manager, temp_project):
        """Test that disabled plugins don't run hooks."""
        plugin = TestPlugin()
        plugin_manager._plugins["disabled-plugin"] = MagicMock(
            info=plugin.info,
            instance=plugin,
            config=PluginConfig(enabled=False),
            enabled=False,
            hooks=[],
        )

        context = HookContext(
            project=temp_project,
            phase="planning",
            feature="test",
        )

        await plugin_manager.execute_phase_hooks("planning", context, "enter")

        assert "entered" not in context.data

    @pytest.mark.asyncio
    async def test_hook_error_doesnt_crash_others(self, plugin_manager, temp_project):
        """Test that one failing hook doesn't stop others."""

        class FailingPlugin(Plugin):
            @property
            def info(self):
                return PluginInfo(name="failing-plugin", version="1.0.0")

            def on_phase_enter(self, context):
                raise RuntimeError("Hook failed!")

        class WorkingPlugin(Plugin):
            @property
            def info(self):
                return PluginInfo(name="working-plugin", version="1.0.0")

            def on_phase_enter(self, context):
                context.data["working"] = True

        failing = FailingPlugin()
        working = WorkingPlugin()

        failing_state = PluginState(
            info=failing.info,
            instance=failing,
            config=PluginConfig(),
            enabled=True,
            hooks=[],
        )
        working_state = PluginState(
            info=working.info,
            instance=working,
            config=PluginConfig(),
            enabled=True,
            hooks=[],
        )
        # Use the plugin's actual names as keys
        plugin_manager._plugins[failing.info.name] = failing_state
        plugin_manager._plugins[working.info.name] = working_state
        # Register hooks properly
        plugin_manager._register_plugin_hooks(failing_state, temp_project)
        plugin_manager._register_plugin_hooks(working_state, temp_project)

        context = HookContext(
            project=temp_project,
            phase="planning",
            feature="test",
        )

        # Should not raise despite failing plugin
        await plugin_manager.execute_phase_hooks("planning", context, "enter")

        # Working plugin should still have run
        assert context.data.get("working") is True


class TestCustomVerification:
    """Test custom verification step integration."""

    def test_get_custom_verification_steps(self, plugin_manager):
        """Test getting custom verification steps from plugins."""
        plugin = VerificationPlugin()
        plugin_manager._plugins["verifier"] = MagicMock(
            info=plugin.info,
            instance=plugin,
            config=PluginConfig(),
            enabled=True,
            hooks=[],
        )

        steps = plugin_manager.get_custom_verification_steps()

        assert len(steps) == 1
        assert steps[0]["name"] == "custom-check"
        assert steps[0]["command"] == "echo 'Custom verification'"

    def test_disabled_plugin_no_steps(self, plugin_manager):
        """Test that disabled plugins don't provide verification steps."""
        plugin = VerificationPlugin()
        plugin_manager._plugins["disabled-verifier"] = MagicMock(
            info=plugin.info,
            instance=plugin,
            config=PluginConfig(enabled=False),
            enabled=False,
            hooks=[],
        )

        steps = plugin_manager.get_custom_verification_steps()

        assert len(steps) == 0

    def test_plugin_without_verification_steps(self, plugin_manager):
        """Test plugin that doesn't provide verification steps."""
        plugin = TestPlugin()
        plugin_manager._plugins["no-verifier"] = MagicMock(
            info=plugin.info,
            instance=plugin,
            config=PluginConfig(),
            enabled=True,
            hooks=[],
        )

        steps = plugin_manager.get_custom_verification_steps()

        assert len(steps) == 0


class TestPluginConfiguration:
    """Test plugin configuration loading."""

    def test_load_plugin_config(self, plugin_manager, tmp_path):
        """Test loading plugin configuration from YAML."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_file = plugins_dir / "configured.py"
        plugin_file.write_text("# Plugin")

        config_file = plugins_dir / "config.yml"
        config_data = {
            "enabled": True,
            "priority": 50,
            "custom_setting": "value",
        }
        config_file.write_text(yaml.dump(config_data))

        config = plugin_manager._load_plugin_config(plugin_file)

        assert config["enabled"] is True
        assert config["priority"] == 50
        assert config["custom_setting"] == "value"

    def test_load_plugin_config_package(self, plugin_manager, tmp_path):
        """Test loading config from plugin package."""
        pkg_dir = tmp_path / "my_plugin"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("# Package")

        config_file = pkg_dir / "config.yml"
        config_data = {"enabled": False}
        config_file.write_text(yaml.dump(config_data))

        config = plugin_manager._load_plugin_config(pkg_dir)

        assert config["enabled"] is False

    def test_load_plugin_config_missing(self, plugin_manager, tmp_path):
        """Test loading config when file doesn't exist."""
        plugin_file = tmp_path / "unconfigured.py"

        config = plugin_manager._load_plugin_config(plugin_file)

        assert config == {}

    def test_load_plugin_config_invalid_yaml(self, plugin_manager, tmp_path):
        """Test loading invalid YAML config."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_file = plugins_dir / "bad_config.py"
        plugin_file.write_text("# Plugin")

        config_file = plugins_dir / "config.yml"
        config_file.write_text("invalid: yaml: [")

        config = plugin_manager._load_plugin_config(plugin_file)

        # Should return empty config on error
        assert config == {}
