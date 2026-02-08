"""MCP Server Configuration Model."""

from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    """Configuration for a remote MCP server."""

    name: str = Field(..., description="Name of the server (must be unique)")
    type: str = Field(..., description="Type of connection: 'stdio' or 'sse'")
    command: str | None = Field(None, description="Command to execute (for stdio type)")
    args: list[str] = Field(default_factory=list, description="Arguments for the command (for stdio type)")
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the command (for stdio type)"
    )
    url: str | None = Field(None, description="URL to connect to (for sse type)")
    disabled: bool = Field(default=False, description="Whether this server is disabled")
