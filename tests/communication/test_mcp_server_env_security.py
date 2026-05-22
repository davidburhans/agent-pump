import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_pump.communication.mcp_server import AgentPumpMCPServer
from agent_pump.models.tool_config import ToolConfig


@pytest.fixture
def mock_app_state():
    mock = MagicMock()
    mock.project_service = MagicMock()
    return mock


@pytest.fixture
def server(mock_app_state):
    return AgentPumpMCPServer(mock_app_state)


@pytest.mark.asyncio
async def test_unsandboxed_tool_does_not_expose_host_secrets(server):
    """
    Test that an unsandboxed tool receives only whitelisted environment
    variables and tool-specific ones.
    Checks that filtering is case-insensitive for Windows compatibility.
    """
    tool_config = ToolConfig(
        name="test_tool",
        description="Test Tool",
        command="echo hello",
        working_dir=".",
        sandbox=False,
        env={"TOOL_VAR": "tool_value"},
    )

    project_path = Path("/tmp/test_project")

    # Mock subprocess
    process_mock = AsyncMock()
    process_mock.pid = 12345
    process_mock.returncode = 0
    process_mock.terminate = MagicMock()
    process_mock.kill = MagicMock()
    process_mock.communicate.return_value = (b"hello\n", b"")

    # Set a sensitive environment variable and a whitelisted one with weird
    # casing (e.g. "Path" common on Windows)
    # Also include a variable that should be whitelisted regardless of case
    mock_environ = {
        "SECRET_KEY": "super_secret_value",
        "Path": "/usr/bin:/bin",  # Mixed case key
        "USER": "testuser",
        "systemroot": "C:\\Windows",  # Lowercase key
    }

    with patch.dict(os.environ, mock_environ, clear=True):
        with (
            patch("asyncio.create_subprocess_exec", return_value=process_mock) as mock_exec,
            patch("agent_pump.utils.subprocess_manager.subprocess_manager.track_process"),
            patch("agent_pump.utils.subprocess_manager.subprocess_manager.untrack_process"),
        ):
            await server._execute_tool(tool_config, [], project_path)

            assert mock_exec.called
            call_args = mock_exec.call_args
            kwargs = call_args.kwargs
            env_arg = kwargs.get("env")
            assert env_arg is not None

            # Assert fix: SECRET_KEY is NOT present in the env passed to subprocess
            assert "SECRET_KEY" not in env_arg

            # Assert whitelisted vars are present regardless of input case
            # Support case insensitivity (especially on Windows where os.environ
            # converts keys to UPPERCASE)
            def get_case_insensitive(d, key):
                for k, v in d.items():
                    if k.upper() == key.upper():
                        return k, v
                return None, None

            path_key, path_val = get_case_insensitive(env_arg, "Path")
            assert path_key is not None
            assert path_val == "/usr/bin:/bin"

            # "USER" (input) -> "USER" (whitelist)
            user_key, user_val = get_case_insensitive(env_arg, "USER")
            assert user_key is not None
            assert user_val == "testuser"

            # "systemroot" (input) -> "systemroot" (whitelist)
            sysroot_key, sysroot_val = get_case_insensitive(env_arg, "systemroot")
            assert sysroot_key is not None
            assert sysroot_val == "C:\\Windows"
