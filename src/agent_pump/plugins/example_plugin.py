"""Example Agent Pump plugin demonstrating all available hooks.

This plugin serves as a reference implementation for creating custom Agent Pump plugins.
It demonstrates how to:
- Hook into workflow phases (enter/exit)
- Hook into verification (start/complete)
- Provide custom verification steps
- Use the event bus for custom events
"""

from __future__ import annotations

from agent_pump.models.plugin import HookContext, PluginInfo
from agent_pump.plugins.base import Plugin, PluginContext


class ExamplePlugin(Plugin):
    """Example plugin demonstrating Agent Pump's plugin API.

    This plugin showcases all available hooks and how to use them effectively.

    To use this plugin:
    1. Copy this file to your project's `.agent-pump/plugins/` directory
    2. Optionally create a `config.yml` in the same directory for configuration
    3. The plugin will be automatically loaded on the next workflow run

    Example config.yml:
        enabled: true
        priority: 50
        custom_setting: "value"
    """

    @property
    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        return PluginInfo(
            name="example-plugin",
            version="1.0.0",
            description="Example plugin demonstrating all Agent Pump hooks",
            author="Your Name",
            email="you@example.com",
            url="https://github.com/yourusername/example-plugin",
            license="MIT",
        )

    def initialize(self, context: PluginContext) -> None:
        """Called when the plugin is loaded.

        Use this to set up resources, subscribe to events, or load configuration.

        Args:
            context: PluginContext with access to event_bus, project_path, and config_path
        """
        super().initialize(context)

        # Access custom configuration from config.yml
        self.custom_setting = self.config.get("custom_setting", "default_value")

        # Log initialization (appears in project logs)
        print(f"ExamplePlugin initialized with setting: {self.custom_setting}")

    def shutdown(self) -> None:
        """Called when the plugin is unloaded.

        Use this to clean up resources, close connections, etc.
        """
        print("ExamplePlugin shutting down")

    def on_phase_enter(self, context: HookContext) -> None:
        """Called when entering a workflow phase.

        This is called before the phase executes, allowing you to:
        - Perform pre-phase setup
        - Modify context data
        - Log phase start
        - Trigger external actions

        Args:
            context: HookContext containing:
                - project: The Project being processed
                - phase: Name of the phase being entered (e.g., "planning", "implementing")
                - feature: Current feature being worked on
                - event_bus: EventBus for publishing events
                - data: Dict for storing/retrieving data between hooks
        """
        phase = context.phase
        feature = context.feature

        print(f"[ExamplePlugin] Entering phase: {phase} for feature: {feature}")

        # Example: Store data for the exit hook
        context.data[f"{phase}_start_time"] = "timestamp_here"

        # Example: Different actions for different phases
        if phase == "planning":
            # Do something before planning starts
            pass
        elif phase == "implementing":
            # Do something before implementation starts
            pass

    def on_phase_exit(self, context: HookContext) -> None:
        """Called when exiting a workflow phase.

        This is called after the phase completes (success or failure), allowing you to:
        - Perform post-phase cleanup
        - Analyze phase results (check context.data.get('success'))
        - Trigger follow-up actions
        - Log phase completion

        Args:
            context: HookContext with additional data:
                - data['success']: Boolean indicating if phase succeeded
                - data['error']: Error message if phase failed
        """
        phase = context.phase
        success = context.data.get("success", False)

        print(f"[ExamplePlugin] Exiting phase: {phase} (success={success})")

        # Example: Check the result and take action
        if not success:
            error = context.data.get("error", "Unknown error")
            print(f"[ExamplePlugin] Phase failed with error: {error}")

    def on_verification_start(self, context: HookContext) -> None:
        """Called before verification commands run.

        Use this to:
        - Perform pre-verification setup
        - Modify verification configuration
        - Log verification start

        Args:
            context: HookContext with project information
        """
        print("[ExamplePlugin] Verification starting")

    def on_verification_complete(self, context: HookContext) -> None:
        """Called after verification commands complete.

        Use this to:
        - Analyze verification results
        - Perform post-verification actions
        - Log verification completion

        Args:
            context: HookContext with additional data:
                - data['all_passed']: Boolean indicating if all checks passed
                - data['results']: Dict of verification results by command
        """
        all_passed = context.data.get("all_passed", False)
        results = context.data.get("results", {})

        print(f"[ExamplePlugin] Verification complete (passed={all_passed})")

        # Example: Process results
        for command, result in results.items():
            print(f"  - {command}: {'PASS' if result else 'FAIL'}")

    def get_custom_verification_steps(self) -> list[dict]:
        """Return custom verification steps to add.

        These steps will be run alongside the standard build/lint/test commands.

        Returns:
            List of verification step dictionaries with keys:
            - name: Step name (displayed in logs)
            - command: Shell command to execute
            - required: Whether step is required (default True)

        Example:
            return [
                {
                    "name": "custom-security-check",
                    "command": "bandit -r src/",
                    "required": True,
                },
                {
                    "name": "custom-linter",
                    "command": "mypy src/",
                    "required": False,  # Won't fail verification if this fails
                },
            ]
        """
        # Example: Add a custom security check (disabled by default)
        if self.config.get("enable_security_check", False):
            return [
                {
                    "name": "example-security-scan",
                    "command": "echo 'Running security scan...'",
                    "required": True,
                }
            ]

        return []


# Optional: Async versions of hooks for async operations
class AsyncExamplePlugin(Plugin):
    """Example of a plugin using async hooks.

    Use async hooks when you need to perform async operations like:
    - HTTP requests
    - Database queries
    - File I/O with async libraries
    """

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="async-example-plugin",
            version="1.0.0",
            description="Example async plugin",
        )

    async def on_phase_enter(self, context: HookContext) -> None:
        """Async version of on_phase_enter.

        Allows performing async operations before phase execution.
        """
        # Example: Fetch external data
        # async with aiohttp.ClientSession() as session:
        #     async with session.get('https://api.example.com/data') as resp:
        #         data = await resp.json()
        #         context.data['external_data'] = data
        pass

    async def on_phase_exit(self, context: HookContext) -> None:
        """Async version of on_phase_exit."""
        pass
