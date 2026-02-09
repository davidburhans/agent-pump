"""Integration tests for verification executor."""

import sys

import pytest

from agent_pump.models.tool_security import ToolSecurityConfig
from agent_pump.models.verification_config import VerificationConfig
from agent_pump.orchestrator.verification_executor import VerificationExecutor

# Get Python executable path with forward slashes for cross-platform shlex compatibility
_PYTHON = sys.executable.replace("\\", "/")


# Cross-platform command helpers using Python
# These work on both Windows and Unix because we invoke the Python interpreter directly
# NOTE: Commands passed to VerificationConfig cannot contain semicolons (security validation),
# so we use tricks to avoid them in multi-statement Python code.
def echo_cmd(text: str) -> str:
    """Return a cross-platform echo command."""
    return f"{_PYTHON} -c \"print('{text}')\""


def fail_cmd() -> str:
    """Return a cross-platform command that always fails."""
    # Use __import__ and exit() to avoid semicolons
    return f'{_PYTHON} -c "exit(1)"'


def sleep_cmd(seconds: float) -> str:
    """Return a cross-platform sleep command."""
    # Use __import__ to avoid semicolons
    return f"{_PYTHON} -c \"__import__('time').sleep({seconds})\""


class TestVerificationExecutor:
    """Tests for VerificationExecutor class."""

    def test_initialization(self, tmp_path):
        """Test initialization of VerificationExecutor."""
        config = VerificationConfig(
            build_cmd="echo build",
            lint_cmd="echo lint",
            test_cmd="echo test",
            skip_verification=False,
        )

        executor = VerificationExecutor(tmp_path, config)
        assert executor.project_path == tmp_path
        assert executor.config == config

    def test_initialization_with_none_config(self, tmp_path):
        """Test initialization with None config."""
        executor = VerificationExecutor(tmp_path, None)
        assert executor.project_path == tmp_path
        assert executor.config == VerificationConfig()

    @pytest.mark.asyncio
    async def test_run_command_success(self, tmp_path):
        """Test running a successful command."""
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, tool_security_config=security_config)

        # Use cross-platform Python command
        cmd = echo_cmd("hello")
        result = await executor.run_command(cmd, timeout=10)

        assert result.success is True
        assert result.command == cmd
        assert "hello" in result.stdout
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.duration > 0

    @pytest.mark.asyncio
    async def test_run_command_failure(self, tmp_path):
        """Test running a command that fails."""
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, tool_security_config=security_config)

        # Use cross-platform fail command
        cmd = fail_cmd()
        result = await executor.run_command(cmd, timeout=10)

        assert result.success is False
        assert result.command == cmd
        assert result.exit_code != 0
        assert result.duration > 0

    @pytest.mark.asyncio
    async def test_run_command_timeout(self, tmp_path):
        """Test running a command that times out."""
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, tool_security_config=security_config)

        # Use cross-platform sleep command that takes longer than timeout
        cmd = sleep_cmd(5)
        result = await executor.run_command(cmd, timeout=1)

        assert result.success is False
        assert result.command == cmd
        assert result.exit_code is None  # Process was terminated
        assert "timed out" in result.stderr.lower()
        assert result.duration > 0

    @pytest.mark.asyncio
    async def test_run_command_not_found(self, tmp_path):
        """Test running a command that doesn't exist."""
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, tool_security_config=security_config)

        # Use a command that doesn't exist
        result = await executor.run_command("nonexistentcommand12345", timeout=10)

        assert result.success is False
        assert result.command == "nonexistentcommand12345"
        assert result.exit_code is None
        assert "not found" in result.stderr.lower() or "No such file" in result.stderr

    @pytest.mark.asyncio
    async def test_run_empty_command(self, tmp_path):
        """Test running an empty command."""
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, tool_security_config=security_config)

        result = await executor.run_command("", timeout=10)

        assert result.success is True
        assert result.command == ""
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.exit_code == 0
        assert result.duration == 0.0

    @pytest.mark.asyncio
    async def test_run_build_method(self, tmp_path):
        """Test the run_build method."""
        config = VerificationConfig(build_cmd=echo_cmd("building"))
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, config, tool_security_config=security_config)

        result = await executor.run_build(timeout=10)

        assert result.success is True
        assert result.command == echo_cmd("building")
        assert "building" in result.stdout

    @pytest.mark.asyncio
    async def test_run_build_method_no_command(self, tmp_path):
        """Test the run_build method when no command is set."""
        config = VerificationConfig(build_cmd=None)
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, config, tool_security_config=security_config)

        result = await executor.run_build(timeout=10)

        assert result.success is True
        assert result.command == ""
        assert "No build command configured" in result.stdout

    @pytest.mark.asyncio
    async def test_run_lint_method(self, tmp_path):
        """Test the run_lint method."""
        config = VerificationConfig(lint_cmd=echo_cmd("linting"))
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, config, tool_security_config=security_config)

        result = await executor.run_lint(timeout=10)

        assert result.success is True
        assert result.command == echo_cmd("linting")
        assert "linting" in result.stdout

    @pytest.mark.asyncio
    async def test_run_test_method(self, tmp_path):
        """Test the run_test method."""
        config = VerificationConfig(test_cmd=echo_cmd("testing"))
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, config, tool_security_config=security_config)

        result = await executor.run_test(timeout=10)

        assert result.success is True
        assert result.command == echo_cmd("testing")
        assert "testing" in result.stdout

    @pytest.mark.asyncio
    async def test_run_coverage_method(self, tmp_path):
        """Test the run_coverage method."""
        config = VerificationConfig(coverage_cmd=echo_cmd("coverage"))
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, config, tool_security_config=security_config)

        result = await executor.run_coverage(timeout=10)

        assert result.success is True
        assert result.command == echo_cmd("coverage")
        assert "coverage" in result.stdout

    @pytest.mark.asyncio
    async def test_run_all_methods_skip_verification(self, tmp_path):
        """Test the run_all method when skip_verification is True."""
        config = VerificationConfig(skip_verification=True)
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, config, tool_security_config=security_config)

        results = await executor.run_all(timeout_per_command=10)

        # All results should indicate success due to skip
        for cmd_type, result in results.items():
            assert result.success is True
            assert "Verification skipped as configured" in result.stdout

    @pytest.mark.asyncio
    async def test_run_all_methods_success(self, tmp_path):
        """Test the run_all method when all commands succeed."""
        config = VerificationConfig(
            build_cmd=echo_cmd("build_success"),
            lint_cmd=echo_cmd("lint_success"),
            test_cmd=echo_cmd("test_success"),
            coverage_cmd=echo_cmd("coverage_success"),
        )
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, config, tool_security_config=security_config)

        results = await executor.run_all(timeout_per_command=10)

        # All results should succeed
        assert len(results) == 4
        assert all(result.success for result in results.values())
        assert "build_success" in results["build"].stdout
        assert "lint_success" in results["lint"].stdout
        assert "test_success" in results["test"].stdout
        assert "coverage_success" in results["coverage"].stdout

    @pytest.mark.asyncio
    async def test_run_all_methods_build_failure(self, tmp_path):
        """Test the run_all method when build command fails."""
        config = VerificationConfig(
            build_cmd=fail_cmd(),  # This will fail
            lint_cmd=echo_cmd("lint_should_not_run"),
            test_cmd=echo_cmd("test_should_not_run"),
            coverage_cmd=echo_cmd("coverage_should_not_run"),
        )
        # Allow unsandboxed execution for tests
        security_config = ToolSecurityConfig(allow_unsandboxed_tools=True)
        executor = VerificationExecutor(tmp_path, config, tool_security_config=security_config)

        results = await executor.run_all(timeout_per_command=10)

        # Build should fail, others should be skipped
        assert results["build"].success is False
        assert results["lint"].success is False
        assert results["test"].success is False
        assert results["coverage"].success is False
        assert "Build failed, skipping lint" in results["lint"].stdout
        assert "Build failed, skipping test" in results["test"].stdout
        assert "Build failed, skipping coverage" in results["coverage"].stdout
