import asyncio
import fnmatch
import json
import logging
import os
import re
import shutil
import sys
import time
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from agent_pump.communication.mcp_client import MCPClientManager
from agent_pump.models.mcp_config import MCPServerConfig
from agent_pump.models.tool_config import ToolConfig
from agent_pump.models.tool_security import ToolSecurityConfig
from agent_pump.utils.execution import SecureExecutor

logger = logging.getLogger(__name__)


class AgentPumpMCPServer:
    def __init__(self, app_state: Any):
        self.server = FastMCP("agent-pump")
        self.app_state = app_state
        self.client_manager = MCPClientManager()
        self._register_tools()
        self._register_resources()

    async def shutdown(self):
        """Shutdown the MCP server and cleanup."""
        await self.client_manager.close()

    @property
    def project_service(self):
        return getattr(self.app_state, "project_service", None)

    def _resolve_project_path(self, project_id: str):
        from pathlib import Path

        project_service = self.project_service
        if not project_service:
            return None

        project_path = None
        try:
            project_path = Path(project_id).resolve()
        except Exception:
            pass

        if not project_path or project_path not in project_service.workflows:
            for p in project_service.workflows:
                if str(p) == project_id:
                    project_path = p
                    break

        if project_path not in project_service.workflows:
            return None

        return project_path

    def _get_remote_tools_config(self, project_path: Any) -> list[MCPServerConfig]:
        """Get remote MCP server configurations for a project."""
        project_service = self.project_service
        if not project_service:
            return []

        workflow = project_service.workflows.get(project_path)
        if not workflow or not workflow.config:
            return []

        configs = []
        if hasattr(workflow.config, "mcp_servers"):
            configs = workflow.config.mcp_servers

        # Apply security policy
        tool_security = (
            workflow.project_config.tool_security
            if workflow.project_config
            else ToolSecurityConfig()
        )

        # If security is enabled (default) and unsandboxed tools are not allowed (default)
        if (
            tool_security
            and tool_security.enabled
            and not tool_security.allow_unsandboxed_tools
        ):
            safe_configs = []
            for config in configs:
                if config.type == "stdio":
                    logger.warning(
                        f"Skipping MCP server '{config.name}' (type=stdio) due to security policy. "
                        "Unsandboxed tools are disabled."
                    )
                    continue
                safe_configs.append(config)
            return safe_configs

        return configs

    def _get_project_tools(self, project_id: str) -> list[ToolConfig]:
        """Get available tools for a project."""
        project_path = self._resolve_project_path(project_id)
        if not project_path:
            return []

        project_service = self.project_service
        if not project_service:
            return []

        workflow = project_service.workflows[project_path]
        # Get tool security config
        tool_security = (
            workflow.project_config.tool_security
            if workflow.project_config
            else ToolSecurityConfig()
        )

        # 1. Tools from config.yml
        tools: list[ToolConfig] = []
        if workflow.config and hasattr(workflow.config, "tools"):
            tools.extend(workflow.config.tools)

        # Apply security policy for explicit tools
        if tool_security and tool_security.enabled and not tool_security.allow_unsandboxed_tools:
            for tool in tools:
                if not tool.sandbox:
                    logger.warning(
                        f"Forcing sandbox for tool {tool.name} due to security policy."
                    )
                    tool.sandbox = True

        # 2. Implicit tools from .agent-pump/tools/
        # Only allow if explicitly enabled in tool security config
        allow_implicit = tool_security and tool_security.allow_implicit_discovery

        tools_dir = project_path / ".agent-pump" / "tools"
        if allow_implicit and tools_dir.exists() and tools_dir.is_dir():
            for item in tools_dir.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    # Check if already defined
                    tool_name = item.stem
                    if any(t.name == tool_name for t in tools):
                        continue

                    # Determine interpreter and command
                    command = None
                    interpreter = None
                    if item.suffix == ".py":
                        command = f"{sys.executable} .agent-pump/tools/{item.name}"
                        interpreter = "python"
                    elif item.suffix in (".sh", ".bash"):
                        # Try to use bash if available, otherwise assume direct execution (linux)
                        command = f"bash .agent-pump/tools/{item.name}"
                        interpreter = "bash" if item.suffix == ".bash" else "sh"
                    elif item.suffix == ".js":
                        command = f"node .agent-pump/tools/{item.name}"
                        interpreter = "node"
                    elif item.suffix == ".ts":
                        command = f"ts-node .agent-pump/tools/{item.name}"
                        interpreter = "node"  # Treat ts-node as node family
                    elif item.suffix in (".bat", ".cmd", ".ps1"):
                        # Windows scripts
                        if item.suffix == ".ps1":
                            command = f"powershell -File .agent-pump/tools/{item.name}"
                            interpreter = "powershell"
                        else:
                            command = f".agent-pump/tools/{item.name}"
                            interpreter = "cmd"

                    # Check allowed interpreters
                    if (
                        tool_security
                        and tool_security.enabled
                        and interpreter
                        and interpreter not in tool_security.allowed_interpreters
                    ):
                        logger.warning(
                            f"Skipping tool {item.name}: Interpreter '{interpreter}' not allowed."
                        )
                        continue

                    if command:
                        tools.append(
                            ToolConfig(
                                name=tool_name,
                                description=f"Execute {item.name}",
                                command=command,
                                working_dir=".",  # relative to project root
                                sandbox=True,
                            )
                        )
        return tools

    def _validate_argument(
        self, value: str, arg_def: Any, tool_security: Any, project_path: Any
    ) -> tuple[bool, str]:
        """Validate a tool argument against configuration."""

        # 1. Regex Validation
        if arg_def.validation_regex:
            if not re.match(arg_def.validation_regex, value):
                return (
                    False,
                    f"Argument '{arg_def.name}' failed regex validation: {value} (Pattern: {arg_def.validation_regex})",
                )

        # 2. Path Validation
        if arg_def.type == "path" and tool_security and tool_security.enabled:
            try:
                # 1. Resolve Path
                resolved_path = (project_path / value).resolve()

                # 2. Check if within project root (canonicalization)
                # We normalize paths to strings for comparison
                # Using commonpath to ensure it's a subpath
                if os.path.commonpath([resolved_path, project_path]) != str(project_path):
                    return False, f"Path traversal attempt detected: {value}"

                # 3. Check allowed patterns
                rel_path = resolved_path.relative_to(project_path)
                # use forward slashes for fnmatch
                rel_path_str = str(rel_path).replace("\\", "/")

                matched = any(
                    fnmatch.fnmatch(rel_path_str, pattern)
                    for pattern in tool_security.allowed_path_patterns
                )
                if not matched:
                    return (
                        False,
                        f"Argument '{arg_def.name}' path not allowed: {value}. Allowed patterns: {tool_security.allowed_path_patterns}",
                    )
            except Exception as e:
                logger.warning(f"Error validating path argument: {e}")
                return False, f"Error validating path: {e}"

        return True, ""

    async def _execute_tool(
        self, tool_config: ToolConfig, args: list[str], project_path: Any
    ) -> str:
        """Execute a tool."""

        # Get security config
        project_service = self.project_service
        workflow = project_service.workflows[project_path] if project_service else None
        tool_security = (
            workflow.project_config.tool_security
            if workflow and workflow.project_config
            else ToolSecurityConfig()
        )

        # Validate arguments
        if tool_security and tool_security.enabled:
            # Ensure argument count does not exceed definition
            if len(args) > len(tool_config.args):
                return f"Security Error: Too many arguments. Expected max {len(tool_config.args)}, got {len(args)}."

            # Map input args list to named args for validation
            for i, arg_val in enumerate(args):
                if i < len(tool_config.args):
                    arg_def = tool_config.args[i]
                    is_valid, error_msg = self._validate_argument(
                        arg_val, arg_def, tool_security, project_path
                    )
                    if not is_valid:
                        return f"Security Error: {error_msg}"

            # If tool is unsandboxed, we MUST enforce stricter argument validation
            # to prevent path traversal on the host filesystem.
            if not tool_config.sandbox:
                # Resolve project path to handle symlinks correctly
                abs_project_path = project_path.resolve()

                # Check all arguments for path traversal patterns regardless of type definition
                for i, arg_val in enumerate(args):
                    # Check for flag arguments (e.g. --file=/path/to/file)
                    check_val = arg_val
                    if arg_val.startswith("-") and "=" in arg_val:
                        parts = arg_val.split("=", 1)
                        if len(parts) == 2:
                            check_val = parts[1]

                    try:
                        # Attempt to resolve the argument as a path relative to the project
                        # resolve() handles symlinks and normalizes ".."
                        resolved_path = (abs_project_path / check_val).resolve()

                        # Check if the resolved path is within the project root
                        if os.path.commonpath([resolved_path, abs_project_path]) != str(abs_project_path):
                            return f"Security Error: Argument {i} '{arg_val}' attempts to escape project root (path traversal)."
                    except OSError:
                        # If resolution fails (e.g. invalid characters, filename too long),
                        # it is likely not a valid path that the tool can use to access files.
                        # We assume it is safe content.
                        pass
                    except Exception as e:
                        logger.warning(f"Unexpected error validating argument {i}: {e}")
                        # Fail safe for unexpected errors, but only if it looks like a path
                        if ".." in check_val or os.path.isabs(check_val):
                            return f"Security Error: Argument {i} could not be validated and looks suspicious."

        command_args = tool_config.get_command_args(args)

        # Determine cwd
        cwd = project_path
        if tool_config.working_dir:
            try:
                # Resolve both paths to ensure we compare absolute paths
                abs_project_path = project_path.resolve()
                resolved_cwd = (project_path / tool_config.working_dir).resolve()

                # Security check: Ensure working_dir is within project root
                if os.path.commonpath([resolved_cwd, abs_project_path]) != str(abs_project_path):
                    return f"Security Error: Tool working_dir '{tool_config.working_dir}' attempts to escape project root."

                cwd = resolved_cwd
            except Exception as e:
                return f"Security Error: Invalid working_dir '{tool_config.working_dir}': {e}"

        # Define allowed environment variables (whitelist)
        # We start with a minimal set to ensure basic functionality
        # while stripping potential secrets.
        ALLOWED_ENV_VARS = {
            # Common
            "PATH",
            "LANG",
            "LC_ALL",
            "TZ",
            "HOME",
            # Windows
            "SYSTEMROOT",
            "COMSPEC",
            "PATHEXT",
            "WINDIR",
            "APPDATA",
            "LOCALAPPDATA",
            "PROGRAMDATA",
            "PROGRAMFILES",
            "PROGRAMFILES(X86)",
            "PSMODULEPATH",
            "USERPROFILE",
            "TEMP",
            "TMP",
            # Linux/Mac
            "USER",
            "SHELL",
            "TERM",
            "TMPDIR",
            "XDG_CACHE_HOME",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
        }

        # Prepare environment
        # Only copy whitelisted variables from host environment
        full_env = {k: v for k, v in os.environ.items() if k.upper() in ALLOWED_ENV_VARS}
        # Apply tool-specific environment variables (these take precedence)
        full_env.update(tool_config.env)

        # Prepare execution arguments for SecureExecutor
        exec_cwd = cwd  # Default to resolved CWD (for unsandboxed)
        exec_working_dir_rel = None
        allow_network = True

        if tool_security and not tool_security.allow_network_access:
            allow_network = False

        if tool_config.sandbox:
            # For sandbox, we must use project_path as cwd (mount source)
            # and pass relative working directory separately
            exec_cwd = project_path
            exec_working_dir_rel = tool_config.working_dir

        # Determine sandbox image with heuristics
        sandbox_image = tool_config.sandbox_image
        if tool_config.sandbox and not sandbox_image:
            cmd_lower = tool_config.command.lower()
            if "python" in cmd_lower or cmd_lower.endswith(".py"):
                sandbox_image = "python:3.11-slim"
            elif "node" in cmd_lower or cmd_lower.endswith(".js") or cmd_lower.endswith(".ts"):
                sandbox_image = "node:18-slim"
            elif "bash" in cmd_lower or "sh " in cmd_lower or cmd_lower.endswith(".sh"):
                sandbox_image = "debian:stable-slim"
            elif "powershell" in cmd_lower or cmd_lower.endswith(".ps1"):
                sandbox_image = "mcr.microsoft.com/powershell"
            else:
                sandbox_image = "python:3.11-slim"  # Default fallback

        try:
            success, stdout, stderr, exit_code, duration = await SecureExecutor.execute_command(
                command=command_args,
                cwd=exec_cwd,
                env=full_env,
                timeout=tool_config.timeout,
                sandbox=tool_config.sandbox,
                sandbox_image=sandbox_image,
                network_access=allow_network,
                working_dir_rel=exec_working_dir_rel,
                inherit_env=False,  # We manually construct full_env with whitelist
            )

            output = []
            if stdout:
                output.append(stdout.strip())
            if stderr:
                output.append(f"STDERR:\n{stderr.strip()}")

            # If exit code is None (e.g. terminated), SecureExecutor usually returns it as None
            if exit_code is not None and exit_code != 0:
                output.append(f"Process exited with code {exit_code}")

            return "\n".join(output)

        except Exception as e:
            return f"Error executing tool: {e}"

    def _register_tools(self):
        @self.server.tool()
        async def signal_decision(
            project_id: str, decision: str, confidence: float, reasoning: str = ""
        ) -> str:
            """Report a decision with confidence score."""
            # Logic to handle decision
            # For now just log or return ack
            return f"Decision received for {project_id}: {decision}"

        @self.server.tool()
        async def request_human_input(
            project_id: str, question: str, options: list[str] | None = None
        ) -> str:
            """Pause workflow and ask the user a question."""
            project_path = self._resolve_project_path(project_id)
            if not project_path:
                return f"Error: Project not found {project_id}"

            project_service = self.project_service
            if not project_service:
                return "Error: Project service not ready"

            workflow = project_service.workflows[project_path]
            try:
                response = await workflow.request_input(question, options)
                return str(response)
            except Exception as e:
                return f"Error requesting input: {str(e)}"

        @self.server.tool()
        async def report_progress(project_id: str, percent: int, message: str) -> str:
            """Report progress to the TUI."""
            # Logic to update progress
            return "Progress updated"

        @self.server.tool()
        async def add_roadmap_item(
            project_id: str, title: str, description: str, priority: str = "medium"
        ) -> str:
            """Add a new item to the project's ROADMAP.md."""
            # Logic to add roadmap item
            return f"Roadmap item added: {title}"

        @self.server.tool()
        async def list_custom_tools(project_id: str) -> str:
            """List available custom tools for the project."""
            tools = self._get_project_tools(project_id)
            return json.dumps([t.model_dump() for t in tools])

        @self.server.tool()
        async def run_custom_tool(
            project_id: str, tool_name: str, arguments: list[str]
        ) -> str:
            """
            Execute a custom tool.

            Args:
                project_id: The project ID or path.
                tool_name: The name of the tool to run.
                arguments: A list of string arguments to pass to the tool.
            """
            project_path = self._resolve_project_path(project_id)
            if not project_path:
                return f"Error: Project not found {project_id}"

            tools = self._get_project_tools(project_id)
            tool = next((t for t in tools if t.name == tool_name), None)

            if not tool:
                return f"Error: Tool '{tool_name}' not found for project {project_id}"

            return await self._execute_tool(tool, arguments, project_path)

        # Register remote tool methods
        self.server.tool()(self.list_remote_tools)
        self.server.tool()(self.run_remote_tool)

    async def list_remote_tools(self, project_id: str) -> str:
        """List available tools from configured remote MCP servers."""
        project_path = self._resolve_project_path(project_id)
        if not project_path:
            return "[]"

        configs = self._get_remote_tools_config(project_path)
        tools = []

        for config in configs:
            try:
                session = await self.client_manager.get_session(config)
                result = await session.list_tools()

                # Convert to list of dicts and add server info
                for t in result.tools:
                    tool_dict = t.model_dump()
                    tool_dict["server"] = config.name
                    tools.append(tool_dict)
            except Exception as e:
                logger.warning(f"Failed to list tools from {config.name}: {e}")

        return json.dumps(tools)

    async def run_remote_tool(
        self, project_id: str, server_name: str, tool_name: str, arguments: dict
    ) -> str:
        """Execute a tool on a remote MCP server."""
        project_path = self._resolve_project_path(project_id)
        if not project_path:
            return f"Error: Project not found {project_id}"

        configs = self._get_remote_tools_config(project_path)
        config = next((c for c in configs if c.name == server_name), None)

        if not config:
            return f"Error: MCP server '{server_name}' not configured for project"

        try:
            session = await self.client_manager.get_session(config)
            result = await session.call_tool(tool_name, arguments)

            # Format result
            output = []
            for content in result.content:
                if content.type == "text":
                    output.append(content.text)
                elif content.type == "image":
                    output.append(f"[Image: {content.mimeType}]")

            return "\n".join(output) if output else "Tool executed successfully."

        except Exception as e:
            return f"Error executing remote tool: {e}"

    def _register_resources(self):
        @self.server.resource("agent_pump://roadmap/{project_id}")
        async def get_roadmap(project_id: str) -> str:
            """Return the parsed ROADMAP.md content."""
            from pathlib import Path

            project_service = self.project_service
            if not project_service:
                return "Error: Project service not ready"

            project_path = None
            try:
                project_path = Path(project_id).resolve()
            except Exception:
                pass

            if not project_path or project_path not in project_service.workflows:
                for p in project_service.workflows:
                    if str(p) == project_id:
                        project_path = p
                        break

            if not project_path:
                return f"Error: Project not found {project_id}"

            roadmap_file = project_path / "ROADMAP.md"
            if roadmap_file.exists():
                return roadmap_file.read_text(encoding="utf-8")
            return "ROADMAP.md not found"

        @self.server.resource("agent_pump://workflow_state/{project_id}")
        async def get_workflow_state(project_id: str) -> str:
            """Return current workflow state as JSON."""
            from pathlib import Path

            project_service = self.project_service
            if not project_service:
                return "{}"

            project_path = None
            try:
                project_path = Path(project_id).resolve()
            except Exception:
                pass

            if not project_path or project_path not in project_service.workflows:
                for p in project_service.workflows:
                    if str(p) == project_id:
                        project_path = p
                        break

            if not project_path:
                return "{}"

            workflow = project_service.workflows[project_path]
            return workflow.workflow_state.model_dump_json(indent=2)

    @property
    def sse_app(self) -> Starlette:
        """Return the SSE app for mounting."""
        return self.server.sse_app

    async def run_stdio(self):
        """Run the MCP server in stdio mode."""
        await self.server.run_stdio_async()
