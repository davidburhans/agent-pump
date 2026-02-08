import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

from agent_pump.models.tool_config import ToolConfig

logger = logging.getLogger(__name__)


class AgentPumpMCPServer:
    def __init__(self, app_state: Any):
        self.server = FastMCP("agent-pump")
        self.app_state = app_state
        self._register_tools()
        self._register_resources()

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

    def _get_project_tools(self, project_id: str) -> list[ToolConfig]:
        """Get available tools for a project."""
        project_path = self._resolve_project_path(project_id)
        if not project_path:
            return []

        project_service = self.project_service
        if not project_service:
            return []

        workflow = project_service.workflows[project_path]

        # 1. Tools from config.yml
        tools: list[ToolConfig] = []
        if workflow.config and hasattr(workflow.config, "tools"):
            tools.extend(workflow.config.tools)

        # 2. Implicit tools from .agent-pump/tools/
        tools_dir = project_path / ".agent-pump" / "tools"
        if tools_dir.exists() and tools_dir.is_dir():
            for item in tools_dir.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    # Check if already defined
                    tool_name = item.stem
                    if any(t.name == tool_name for t in tools):
                        continue

                    # Determine interpreter and command
                    command = None
                    if item.suffix == ".py":
                        command = f"{sys.executable} .agent-pump/tools/{item.name}"
                    elif item.suffix in (".sh", ".bash"):
                        # Try to use bash if available, otherwise assume direct execution (linux)
                        command = f"bash .agent-pump/tools/{item.name}"
                    elif item.suffix == ".js":
                        command = f"node .agent-pump/tools/{item.name}"
                    elif item.suffix == ".ts":
                        command = f"ts-node .agent-pump/tools/{item.name}"
                    elif item.suffix in (".bat", ".cmd", ".ps1"):
                        # Windows scripts
                        if item.suffix == ".ps1":
                            command = f"powershell -File .agent-pump/tools/{item.name}"
                        else:
                            command = f".agent-pump/tools/{item.name}"

                    if command:
                        tools.append(
                            ToolConfig(
                                name=tool_name,
                                description=f"Execute {item.name}",
                                command=command,
                                working_dir=".",  # relative to project root
                            )
                        )
        return tools

    async def _execute_tool(
        self, tool_config: ToolConfig, args: list[str], project_path: Any
    ) -> str:
        """Execute a tool."""
        import os

        command_args = tool_config.get_command_args(args)

        # Determine cwd
        cwd = project_path
        if tool_config.working_dir:
            cwd = project_path / tool_config.working_dir

        env = tool_config.env.copy()
        full_env = os.environ.copy()
        full_env.update(env)

        cmd_str = " ".join(command_args)
        logger.info(f"Executing tool {tool_config.name}: {cmd_str} in {cwd}")

        try:
            process = await asyncio.create_subprocess_exec(
                *command_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=full_env,
            )

            stdout, stderr = await process.communicate()

            output = []
            if stdout:
                output.append(stdout.decode().strip())
            if stderr:
                output.append(f"STDERR:\n{stderr.decode().strip()}")

            if process.returncode != 0:
                output.append(f"Process exited with code {process.returncode}")

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
