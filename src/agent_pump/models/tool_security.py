"""Tool security configuration."""

from pydantic import BaseModel, Field


class ToolSecurityConfig(BaseModel):
    """Configuration for tool security."""

    enabled: bool = Field(default=True, description="Whether tool security checks are enabled")
    allowed_interpreters: list[str] = Field(
        default=["python", "node", "bash", "sh", "powershell", "cmd"],
        description="List of allowed interpreters/commands",
    )
    allowed_path_patterns: list[str] = Field(
        default=["**"], description="List of glob patterns for allowed file access"
    )
    allow_network_access: bool = Field(
        default=True, description="Whether to allow network access in sandboxed environments"
    )
    allow_implicit_discovery: bool = Field(
        default=False,
        description="Whether to automatically discover and execute tools from .agent-pump/tools/",
    )
