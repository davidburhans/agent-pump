from typing import TYPE_CHECKING

from textual.command import Hit, Hits, Provider

if TYPE_CHECKING:
    from agent_pump.tui.app import AgentPumpApp


class AgentPumpCommandProvider(Provider):
    """Command provider for Agent Pump."""

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)

        # We assume this provider is attached to AgentPumpApp
        app = self.app
        # Type hint for development, effectively
        # app: "AgentPumpApp" = self.app  # type: ignore

        # Define commands with their display name, action method name, and help text
        # Using string method names allows getattr to handle potentially missing methods safely
        # although in this specific app they should exist.
        command_defs = [
            ("Add Project", "action_add_project", "Add a new project to the workspace"),
            ("Toggle Dark Mode", "action_toggle_dark", "Switch between light and dark themes"),
            ("Open Settings", "action_open_settings", "Configure global application settings"),
            ("Manage Roadmap", "action_manage_roadmap", "View and manage the project roadmap"),
            ("Add Idea", "action_add_idea", "Add a new idea to the backlog"),
            ("Configure Backends", "action_config_backends", "Configure AI backends for the project"),
            ("Configure Prompts", "action_config_prompts", "Customize prompts for the project"),
            ("Global Prompts", "action_global_prompts", "Configure global prompt templates"),
            ("Filter Logs", "action_filter_logs", "Filter the activity log"),
            ("Toggle Workflow Panel", "action_toggle_workflow_panel", "Show/hide the workflow visualization"),
            ("Toggle Timer Mode", "action_toggle_timer", "Switch between elapsed time and time remaining"),
            ("Update Configuration", "action_update_config", "Reload configuration from disk"),
            ("Start All Projects", "action_start_all", "Start workflow for all loaded projects"),
            ("Stop All Projects", "action_stop_all", "Stop workflow for all loaded projects"),
        ]

        for name, method_name, help_text in command_defs:
            score = matcher.match(name)
            if score > 0:
                # Retrieve the action method from the app
                action = getattr(app, method_name, None)
                if action:
                    yield Hit(
                        score,
                        matcher.highlight(name),
                        action,
                        help=help_text,
                    )
