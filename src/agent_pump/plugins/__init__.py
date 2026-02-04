"""Plugin system for Agent Pump.

This package provides the plugin infrastructure for extending
Agent Pump with custom functionality.
"""

from agent_pump.plugins.base import (
    Plugin,
    PluginContext,
    VerificationHooks,
    WorkflowHooks,
)

__all__ = [
    "Plugin",
    "PluginContext",
    "VerificationHooks",
    "WorkflowHooks",
]
