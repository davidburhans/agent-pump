from agent_pump.models.tool_config import ToolArgument, ToolConfig


def test_tool_config_command_splitting():
    """Test that command string is split correctly, respecting quotes."""
    config = ToolConfig(
        name="test-tool",
        description="A test tool",
        command="python -c \"print('hello world')\"",
    )

    # Current implementation uses .split(), which will fail this check
    # Expected: ['python', '-c', "print('hello world')"]
    # Actual: ['python', '-c', '"print(\'hello', 'world\')"']

    args = config.get_command_args([])
    assert args == ["python", "-c", "print('hello world')"]


def test_tool_config_with_args_list():
    """Test that additional arguments are appended correctly."""
    config = ToolConfig(
        name="echo",
        description="echo tool",
        command='echo "hello world"',
    )

    input_args = ["extra", "arg"]
    args = config.get_command_args(input_args)
    assert args == ["echo", "hello world", "extra", "arg"]


def test_tool_config_with_args_dict():
    """Test mapping dictionary arguments to flags."""
    config = ToolConfig(
        name="test",
        description="test",
        command="cmd",
        args=[
            ToolArgument(name="file", type="string"),
            ToolArgument(name="force", type="boolean"),
        ],
    )

    input_args = {"file": "test.txt", "force": "true"}
    args = config.get_command_args(input_args)

    # Current logic: appends --key value
    assert "--file" in args
    assert "test.txt" in args
    assert "--force" in args
    assert "true" in args
