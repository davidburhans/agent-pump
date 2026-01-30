from typing import TYPE_CHECKING

from textual.command import Hit, Hits, Provider

if TYPE_CHECKING:
    pass


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

        # Global commands always available
        global_commands = [
            ("Add Project", "action_add_project", "Add a new project to the workspace"),
            ("Toggle Dark Mode", "action_toggle_dark", "Switch between light and dark themes"),
            ("Open Settings", "action_open_settings", "Configure global application settings"),
            ("Add Idea", "action_add_idea", "Add a new idea to the backlog"),
            ("Global Prompts", "action_global_prompts", "Configure global prompt templates"),
            ("Filter Logs", "action_filter_logs", "Filter the activity log"),
            (
                "Toggle Workflow Panel",
                "action_toggle_workflow_panel",
                "Show/hide the workflow visualization",
            ),
            (
                "Toggle Timer Mode",
                "action_toggle_timer",
                "Switch between elapsed time and time remaining",
            ),
            (
                "Toggle Sort Order",
                "action_toggle_sort",
                "Toggle log sort order (oldest/newest first)",
            ),
            ("Start All Projects", "action_start_all", "Start workflow for all loaded projects"),
            ("Stop All Projects", "action_stop_all", "Stop workflow for all loaded projects"),
            ("Quit Application", "action_quit", "Quit the application"),
        ]

        # Project specific commands (only available when a project is selected)
        project_commands = []
        if getattr(app, "selected_project", None):
            project_commands = [
                (
                    "Toggle Project State",
                    "action_toggle_project_state",
                    "Start/Stop the selected project",
                ),
                (
                    "Manage Roadmap",
                    "action_manage_roadmap",
                    "View and manage the project roadmap",
                ),
                (
                    "Configure Backends",
                    "action_config_backends",
                    "Configure AI backends for the project",
                ),
                (
                    "Configure Prompts",
                    "action_config_prompts",
                    "Customize prompts for the project",
                ),
                (
                    "Update Configuration",
                    "action_update_config",
                    "Reload configuration from disk",
                ),
                ("Remove Project", "action_remove_project", "Remove the selected project"),
                ("Start Selected", "action_start_selected", "Start the selected project"),
                ("Stop Selected", "action_stop_selected", "Stop the selected project"),
                (
                    "Skip Feature",
                    "action_skip_feature",
                    "Skip the current feature (mark as failed)",
                ),
                (
                    "Configure Project",
                    "action_config_project",
                    "Configure selected project settings",
                ),
                (
                    "Reset Project",
                    "action_reset_project",
                    "Reset workflow state for selected project",
                ),
            ]

        for name, method_name, help_text in global_commands + project_commands:
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
