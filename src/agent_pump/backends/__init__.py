"""Agent backends package - extensible AI coding agent integrations."""

from agent_pump.backends.base import AgentBackend, AgentResult
from agent_pump.backends.gemini import GeminiBackend

__all__ = ["AgentBackend", "AgentResult", "GeminiBackend"]
