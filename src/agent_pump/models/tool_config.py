"""Configuration models for custom tools."""

import shlex
from typing import Any

from pydantic import BaseModel, Field


class ToolArgument(BaseModel):
    """Configuration for a tool argument."""

    name: str = Field(description="Name of the argument")
    type: str = Field(default="string", description="Type of the argument (string, integer, etc.)")
    description: str | None = Field(default=None, description="Description of the argument")
    required: bool = Field(default=True, description="Whether the argument is required")
    validation_regex: str | None = Field(
        default=None, description="Optional regex pattern to validate the argument"
    )


class ToolConfig(BaseModel):
    """Configuration for a custom tool."""

    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    command: str = Field(description="Command to execute")
    working_dir: str | None = Field(
        default=None, description="Working directory for execution (relative to project root)"
    )
    env: dict[str, str] = Field(default_factory=dict, description="Environment variables to set")
    args: list[ToolArgument] = Field(
        default_factory=list, description="Arguments accepted by the tool"
    )
    sandbox: bool = Field(
        default=False, description="Whether to execute the tool in a sandboxed environment"
    )
    sandbox_image: str | None = Field(
        default=None, description="Docker image to use for sandboxing (e.g. 'python:3.11-slim')"
    )

    def get_command_args(self, input_args: dict[str, Any] | list[str]) -> list[str]:
        """
        Construct the command line arguments from input.

        If input_args is a list, it's appended directly.
        If input_args is a dict, we might need a strategy to map it to CLI flags.
        For now, we assume simple script execution where args are passed positionally
        or as flags depending on implementation.

        To keep it simple for scripts:
        If args are defined in config, we expect named arguments.
        But mapping named args to CLI is complex (flags? positionals?).

        Let's assume for scripts, we pass arguments as environment variables
        OR we append them if they are passed as a list.

        If the user provides a list of strings, we append them.
        If the user provides a dict, we try to map them to flags like --key value.
        """
        cmd_parts = shlex.split(self.command)

        if isinstance(input_args, list):
            cmd_parts.extend([str(a) for a in input_args])
        elif isinstance(input_args, dict):
            for key, value in input_args.items():
                # Check if this arg is defined
                arg_def = next((a for a in self.args if a.name == key), None)
                if arg_def:
                    # Simple flag mapping: --name value
                    cmd_parts.append(f"--{key}")
                    cmd_parts.append(str(value))

        return cmd_parts
