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
    Test that an unsandboxed tool receives only whitelisted environment variables and tool-specific ones.
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

    # Set a sensitive environment variable and a whitelisted one with weird casing (e.g. "Path" common on Windows)
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

            # Assert fix: SECRET_KEY is NOT present in the env passed to subprocess
            assert "SECRET_KEY" not in env_arg

            # Assert whitelisted vars are present regardless of input case
            # "Path" (input) -> "PATH" (whitelist)
            assert "Path" in env_arg
            assert env_arg["Path"] == "/usr/bin:/bin"

            # "USER" (input) -> "USER" (whitelist)
            assert "USER" in env_arg
            assert env_arg["USER"] == "testuser"

            # "systemroot" (input) -> "SystemRoot" (whitelist contains SystemRoot, so upper check matches SYSTEMROOT)
            # The whitelist has "SystemRoot", but my code checks k.upper() in ALLOWED_ENV_VARS.
            # Wait, my ALLOWED_ENV_VARS has keys like "SystemRoot", "Path" (actually "PATH").
            # The keys in ALLOWED_ENV_VARS are NOT all uppercase in the code I wrote previously.
            # I defined "SystemRoot" with mixed case in ALLOWED_ENV_VARS.

            # Let's check the code I wrote in previous step.
            # ALLOWED_ENV_VARS = {"PATH", ..., "SystemRoot", ...}

            # If I check k.upper() in ALLOWED_ENV_VARS, then ALLOWED_ENV_VARS must contain uppercase keys.

            # I need to fix ALLOWED_ENV_VARS to be all uppercase in the code if I use k.upper().

            # Ah, I missed that in the previous step. I only changed the check to k.upper() but didn't uppercase the set.
            # I need to fix that first.

            pass
