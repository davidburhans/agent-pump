from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette


class AgentPumpMCPServer:
    def __init__(self, app_state: Any):
        self.server = FastMCP("agent-pump")
        self.app_state = app_state
        self._register_tools()
        self._register_resources()

    @property
    def project_service(self):
        return getattr(self.app_state, "project_service", None)

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
            from pathlib import Path

            try:
                project_path = Path(project_id).resolve()
            except Exception:
                return f"Error: Invalid project path {project_id}"

            project_service = self.project_service
            if not project_service:
                return "Error: Project service not ready"

            if project_path not in project_service.workflows:
                # Try to match by string
                found = False
                for p, w in project_service.workflows.items():
                    if str(p) == project_id:
                        project_path = p
                        found = True
                        break
                if not found:
                    return f"Error: Project workflow not found for {project_id}"

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
