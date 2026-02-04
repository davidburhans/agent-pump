"""Tests for plugin system models."""

import pytest
from pydantic import ValidationError

from agent_pump.models.plugin import (
    HookContext,
    PluginConfig,
    PluginInfo,
    PluginLoadError,
    PluginState,
    RegisteredHook,
)
from agent_pump.models.project import Project, ProjectStatus


class TestPluginInfo:
    """Test PluginInfo model."""

    def test_create_minimal(self):
        """Test creating PluginInfo with minimal data."""
        info = PluginInfo(name="test-plugin")

        assert info.name == "test-plugin"
        assert info.version == "1.0.0"  # Default
        assert info.description == ""
        assert info.author == ""
        assert info.email == ""
        assert info.url == ""
        assert info.license == "MIT"
        assert info.requires == []

    def test_create_full(self):
        """Test creating PluginInfo with all fields."""
        info = PluginInfo(
            name="full-plugin",
            version="2.1.0",
            description="A test plugin",
            author="Test Author",
            email="test@example.com",
            url="https://example.com/plugin",
            license="Apache-2.0",
            requires=[">=1.0.0"],
        )

        assert info.name == "full-plugin"
        assert info.version == "2.1.0"
        assert info.description == "A test plugin"
        assert info.author == "Test Author"
        assert info.email == "test@example.com"
        assert info.url == "https://example.com/plugin"
        assert info.license == "Apache-2.0"
        assert info.requires == [">=1.0.0"]

    def test_name_required(self):
        """Test that name is required."""
        with pytest.raises(ValidationError):
            PluginInfo()

    def test_immutable(self):
        """Test that PluginInfo is immutable."""
        info = PluginInfo(name="test")

        with pytest.raises(ValidationError):
            info.name = "new-name"


class TestPluginConfig:
    """Test PluginConfig model."""

    def test_defaults(self):
        """Test default values."""
        config = PluginConfig()

        assert config.enabled is True
        assert config.priority == 100

    def test_custom_values(self):
        """Test custom configuration values."""
        config = PluginConfig(enabled=False, priority=50)

        assert config.enabled is False
        assert config.priority == 50

    def test_extra_fields(self):
        """Test that extra fields are allowed."""
        config = PluginConfig(custom_key="custom_value", another_field=123)

        assert config.custom_key == "custom_value"
        assert config.another_field == 123


class TestHookContext:
    """Test HookContext model."""

    def test_create(self, tmp_path):
        """Test creating HookContext."""
        project = Project(
            path=tmp_path,
            name="test-project",
            status=ProjectStatus.IDLE,
        )

        context = HookContext(
            project=project,
            phase="planning",
            feature="test-feature",
        )

        assert context.project == project
        assert context.phase == "planning"
        assert context.feature == "test-feature"
        assert context.event_bus is None
        assert context.data == {}

    def test_with_event_bus(self, tmp_path):
        """Test HookContext with event bus."""
        from agent_pump.events.bus import EventBus

        project = Project(
            path=tmp_path,
            name="test",
            status=ProjectStatus.IDLE,
        )
        event_bus = EventBus()

        context = HookContext(
            project=project,
            phase="implementing",
            feature="feature-1",
            event_bus=event_bus,
            data={"key": "value"},
        )

        assert context.event_bus == event_bus
        assert context.data == {"key": "value"}

    def test_data_mutation(self, tmp_path):
        """Test that data dict can be mutated."""
        project = Project(
            path=tmp_path,
            name="test",
            status=ProjectStatus.IDLE,
        )

        context = HookContext(
            project=project,
            phase="planning",
            feature="test",
        )

        # Should be able to modify data
        context.data["new_key"] = "new_value"
        assert context.data["new_key"] == "new_value"


class TestRegisteredHook:
    """Test RegisteredHook dataclass."""

    def test_create(self):
        """Test creating a registered hook."""

        def callback(context):
            pass

        hook = RegisteredHook(
            plugin_name="test-plugin",
            phase="planning",
            callback=callback,
            priority=50,
        )

        assert hook.plugin_name == "test-plugin"
        assert hook.phase == "planning"
        assert hook.callback == callback
        assert hook.priority == 50

    def test_default_priority(self):
        """Test default priority value."""
        hook = RegisteredHook(
            plugin_name="test",
            phase=None,
            callback=lambda x: x,
        )

        assert hook.priority == 100

    def test_all_phases(self):
        """Test hook for all phases."""
        hook = RegisteredHook(
            plugin_name="test",
            phase=None,
            callback=lambda x: x,
        )

        assert hook.phase is None


class TestPluginState:
    """Test PluginState dataclass."""

    def test_create(self):
        """Test creating PluginState."""
        info = PluginInfo(name="test", version="1.0.0")
        config = PluginConfig()

        class FakePlugin:
            pass

        plugin = FakePlugin()

        state = PluginState(
            info=info,
            instance=plugin,
            config=config,
        )

        assert state.info == info
        assert state.instance == plugin
        assert state.config == config
        assert state.enabled is True
        assert state.hooks == []

    def test_with_hooks(self):
        """Test PluginState with hooks."""
        info = PluginInfo(name="test")
        config = PluginConfig()

        class FakePlugin:
            pass

        hooks = [
            RegisteredHook(
                plugin_name="test",
                phase="planning",
                callback=lambda x: x,
            )
        ]

        state = PluginState(
            info=info,
            instance=FakePlugin(),
            config=config,
            hooks=hooks,
            enabled=False,
        )

        assert len(state.hooks) == 1
        assert state.enabled is False


class TestPluginLoadError:
    """Test PluginLoadError exception."""

    def test_raise(self):
        """Test raising PluginLoadError."""
        with pytest.raises(PluginLoadError) as exc_info:
            raise PluginLoadError("Failed to load plugin")

        assert "Failed to load plugin" in str(exc_info.value)

    def test_raise_with_cause(self):
        """Test raising with chained exception."""
        try:
            raise ValueError("Original error")
        except ValueError as e:
            with pytest.raises(PluginLoadError) as exc_info:
                raise PluginLoadError("Plugin failed") from e

        assert "Plugin failed" in str(exc_info.value)
