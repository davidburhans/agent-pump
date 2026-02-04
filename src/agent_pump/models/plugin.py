"""Plugin system models for Agent Pump.

This module defines the data models for the plugin system including
plugin metadata, configuration, and hook context.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from agent_pump.events.bus import EventBus
    from agent_pump.models.project import Project
    from agent_pump.orchestrator.workflow import ProjectWorkflow
    from agent_pump.plugins.base import Plugin


class PluginInfo(BaseModel):
    """Metadata about a plugin.

    Attributes:
        name: Unique plugin name
        version: Plugin version (semver)
        description: Human-readable description
        author: Plugin author name
        email: Author email
        url: Plugin homepage/repository
        license: License identifier
        requires: List of required Agent Pump versions
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Unique plugin name")
    version: str = Field(default="1.0.0", description="Plugin version (semver)")
    description: str = Field(default="", description="Human-readable description")
    author: str = Field(default="", description="Plugin author name")
    email: str = Field(default="", description="Author email")
    url: str = Field(default="", description="Plugin homepage/repository")
    license: str = Field(default="MIT", description="License identifier")
    requires: list[str] = Field(
        default_factory=list,
        description="Required Agent Pump versions",
    )


class PluginConfig(BaseModel):
    """Configuration for a plugin.

    Plugins can define their own configuration schema by subclassing
    this class and adding their own fields.
    """

    model_config = ConfigDict(extra="allow")

    enabled: bool = Field(default=True, description="Whether plugin is enabled")
    priority: int = Field(
        default=100,
        description="Plugin priority (lower = earlier execution)",
    )


class HookContext:
    """Context passed to hook callbacks.

    This is intentionally a plain Python class (not a Pydantic model)
    to avoid circular import issues with Project and EventBus.

    Attributes:
        project: The project being processed
        phase: Current workflow phase name
        feature: Current feature being worked on
        event_bus: Event bus for publishing/subscribing
        data: Additional data for the hook
    """

    def __init__(
        self,
        project: Any,  # Project type - use Any to avoid circular import
        phase: str,
        feature: str | None,
        event_bus: Any | None = None,  # EventBus type - use Any
        data: dict[str, Any] | None = None,
    ) -> None:
        self.project = project
        self.phase = phase
        self.feature = feature
        self.event_bus = event_bus
        self.data = data or {}


class PluginLoadError(Exception):
    """Raised when a plugin fails to load."""

    pass


class PluginHookError(Exception):
    """Raised when a plugin hook fails."""

    pass


@dataclass
class RegisteredHook:
    """Internal representation of a registered hook."""

    plugin_name: str
    phase: str | None  # None = all phases
    callback: Callable[[HookContext], Any]
    priority: int = 100


@dataclass
class PluginState:
    """Runtime state of a loaded plugin."""

    info: PluginInfo
    instance: Any  # Plugin instance - use Any to avoid circular import issues
    config: PluginConfig
    hooks: list[RegisteredHook] = field(default_factory=list)
    enabled: bool = True
