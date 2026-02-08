"""Tests for tool configuration models."""

import pytest
from pydantic import ValidationError

from agent_pump.models.tool_config import ToolArgument, ToolConfig


def test_tool_argument_validation():
    """Test ToolArgument validation."""
    # Valid
    arg = ToolArgument(name="test_arg", type="string")
    assert arg.name == "test_arg"
    assert arg.required is True

    # Missing name
    with pytest.raises(ValidationError):
        ToolArgument(type="string")  # type: ignore


def test_tool_config_validation():
    """Test ToolConfig validation."""
    # Valid
    config = ToolConfig(
        name="my_tool",
        description="A test tool",
        command="./script.sh"
    )
    assert config.name == "my_tool"
    assert config.command == "./script.sh"
    assert config.args == []
    assert config.env == {}

    # With args
    config = ToolConfig(
        name="my_tool",
        description="A test tool",
        command="./script.sh",
        args=[ToolArgument(name="arg1")]
    )
    assert len(config.args) == 1
    assert config.args[0].name == "arg1"


def test_get_command_args_list():
    """Test get_command_args with list input."""
    config = ToolConfig(
        name="my_tool",
        description="test",
        command="./script.sh"
    )

    cmd = config.get_command_args(["arg1", "arg2"])
    assert cmd == ["./script.sh", "arg1", "arg2"]


def test_get_command_args_dict():
    """Test get_command_args with dict input."""
    config = ToolConfig(
        name="my_tool",
        description="test",
        command="./script.sh",
        args=[
            ToolArgument(name="env", type="string"),
            ToolArgument(name="verbose", type="boolean")
        ]
    )

    # Matching args
    cmd = config.get_command_args({"env": "prod", "verbose": "true"})
    assert cmd == ["./script.sh", "--env", "prod", "--verbose", "true"]

    # Extra args ignored (current implementation)
    cmd = config.get_command_args({"env": "prod", "extra": "foo"})
    assert cmd == ["./script.sh", "--env", "prod"]
