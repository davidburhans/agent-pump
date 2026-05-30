"""Agent backends package - extensible AI coding agent integrations."""

from agent_pump.backends.availability import (
    BackendAvailability,
    BackendStatus,
    check_all_backends,
    get_available_backend_names,
)
from agent_pump.backends.base import AgentBackend, AgentResult, BackendError
from agent_pump.backends.claude import ClaudeBackend
from agent_pump.backends.fallback import FallbackBackendRunner
from agent_pump.backends.gemini import GeminiBackend
from agent_pump.backends.ollama import OllamaBackend
from agent_pump.backends.opencode import OpenCodeBackend
from agent_pump.backends.opencode_api import OpenCodeAPIBackend
from agent_pump.backends.pi import PiBackend
from agent_pump.backends.qwen import QwenBackend

# Registry of available backends by name
BACKEND_REGISTRY: dict[str, type[AgentBackend]] = {
    "gemini": GeminiBackend,
    "claude": ClaudeBackend,
    "ollama": OllamaBackend,
    "opencode": OpenCodeBackend,
    "opencode-api": OpenCodeAPIBackend,
    "pi": PiBackend,
    "qwen": QwenBackend,
}


def get_backend(name: str) -> AgentBackend:
    """
    Get a backend instance by name.

    Args:
        name: Backend name (e.g., "gemini", "claude", "opencode")

    Returns:
        An instance of the requested backend

    Raises:
        ValueError: If backend name is not recognized
    """
    if name not in BACKEND_REGISTRY:
        available = list(BACKEND_REGISTRY.keys())
        raise ValueError(f"Unknown backend: '{name}'. Available: {available}")
    return BACKEND_REGISTRY[name]()


def create_fallback_runner(backend_names: list[str]) -> FallbackBackendRunner:
    """
    Create a fallback runner from a list of backend names.

    Args:
        backend_names: Names of backends to try in order

    Returns:
        A FallbackBackendRunner configured with the specified backends
    """
    backends = [get_backend(name) for name in backend_names]
    return FallbackBackendRunner(backends)


def create_fallback_runner_from_config(backend_instances: list) -> FallbackBackendRunner:
    """
    Create a fallback runner from BackendInstance configs.

    Args:
        backend_instances: List of BackendInstance with name and args

    Returns:
        A FallbackBackendRunner configured with the specified backends and their args
    """
    return FallbackBackendRunner.from_config(backend_instances)


__all__ = [
    "AgentBackend",
    "AgentResult",
    "BackendAvailability",
    "BackendError",
    "BackendStatus",
    "BACKEND_REGISTRY",
    "ClaudeBackend",
    "FallbackBackendRunner",
    "GeminiBackend",
    "OllamaBackend",
    "OpenCodeBackend",
    "OpenCodeAPIBackend",
    "PiBackend",
    "QwenBackend",
    "check_all_backends",
    "create_fallback_runner",
    "create_fallback_runner_from_config",
    "get_available_backend_names",
    "get_backend",
]
