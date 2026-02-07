"""Workflow definition models for extensible state machines.

This module provides the abstraction layer for defining custom workflow
state machines. The default 5-phase workflow is defined here, and users
can create custom workflows stored in workspace configuration.
"""

from pydantic import BaseModel, Field


class WorkflowPhase(BaseModel):
    """A single phase in a workflow.

    Represents one step in the development workflow, with its prompt
    configuration and transition rules.
    """

    name: str = Field(description="Phase name (e.g., 'planning', 'implementing')")
    description: str = Field(default="", description="Human-readable description")
    icon: str = Field(default="", description="Emoji icon for TUI display")

    on_success: str = Field(description="State to transition to on success")
    on_failure: str = Field(
        default="error",
        description="State to transition to on failure",
    )
    allow_failure_recovery: bool = Field(
        default=True,
        description="Whether to attempt recovery on failure (vs immediate error)",
    )

    # Extended configuration for custom workflows
    timeout: int | None = Field(
        default=None,
        description="Phase-specific timeout in seconds (None = use global default)",
    )
    max_retries: int = Field(
        default=0,
        description="Number of retry attempts on failure",
        ge=0,
    )
    retry_delay: float = Field(
        default=0.0,
        description="Delay between retries in seconds",
        ge=0.0,
    )
    allow_failure_recovery: bool = Field(
        default=True,
        description="Whether to attempt recovery on failure (vs immediate error)",
    )


class WorkflowDefinition(BaseModel):
    """A complete workflow state machine definition.

    Defines all the states, phases, and transitions for a workflow.
    Custom workflows are stored in workspace configuration.
    """

    name: str = Field(description="Unique workflow name")
    description: str = Field(default="", description="Human-readable description")
    initial_state: str = Field(default="idle", description="Starting state")
    terminal_states: list[str] = Field(
        default_factory=lambda: ["completed", "error"],
        description="States that end workflow execution",
    )
    phases: list[WorkflowPhase] = Field(
        default_factory=list,
        description="Ordered list of workflow phases",
    )

    def get_states(self) -> list[str]:
        """Get all states in this workflow.

        Returns:
            List of state names including idle, phases, and terminal states.
        """
        states = [self.initial_state]
        for phase in self.phases:
            if phase.name not in states:
                states.append(phase.name)
        for terminal in self.terminal_states:
            if terminal not in states:
                states.append(terminal)
        return states

    def get_transitions(self) -> list[dict]:
        """Generate pytransitions-compatible transition list.

        Returns:
            List of transition dicts for pytransitions Machine.
        """
        transitions = []

        # Start transition (idle -> first phase)
        if self.phases:
            transitions.append(
                {
                    "trigger": "start",
                    "source": self.initial_state,
                    "dest": self.phases[0].name,
                }
            )

        # Phase transitions
        for phase in self.phases:
            # Success transition
            transitions.append(
                {
                    "trigger": f"{phase.name}_complete",
                    "source": phase.name,
                    "dest": phase.on_success,
                }
            )
            # Failure transition
            if phase.on_failure:
                transitions.append(
                    {
                        "trigger": f"{phase.name}_failed",
                        "source": phase.name,
                        "dest": phase.on_failure,
                    }
                )

        # Error recovery
        if "error" in self.terminal_states:
            transitions.append(
                {
                    "trigger": "reset",
                    "source": "error",
                    "dest": self.initial_state,
                }
            )

        if "completed" in self.terminal_states:
            dest = self.phases[0].name if self.phases else self.initial_state
            transitions.append(
                {
                    "trigger": "restart",
                    "source": "completed",
                    "dest": dest,
                }
            )

        # Completion transition from last phase (if looping)
        if self.phases and self.phases[-1].on_success == self.phases[0].name:
            # Loop workflow - add no_more_features to any phase to allow breaking the loop
            for phase in self.phases:
                transitions.append(
                    {
                        "trigger": "no_more_features",
                        "source": phase.name,
                        "dest": "completed",
                    }
                )

        return transitions

    def get_phase(self, name: str) -> WorkflowPhase | None:
        """Get a phase by name.

        Args:
            name: Phase name

        Returns:
            The phase, or None if not found.
        """
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None

    def get_phase_icon(self, name: str) -> str:
        """Get the icon for a phase.

        Args:
            name: Phase name

        Returns:
            Icon string, or empty if not found.
        """
        phase = self.get_phase(name)
        return phase.icon if phase else ""


# Default 6-phase workflow
DEFAULT_WORKFLOW = WorkflowDefinition(
    name="default",
    description="Standard 6-phase development workflow: Plan → Implement → Verify → Brainstorm → Commit → Review",  # noqa: E501
    initial_state="idle",
    terminal_states=["completed", "error"],
    phases=[
        WorkflowPhase(
            name="planning",
            description="Creates ENGINEERING_PLAN.md from ROADMAP.md",
            icon="📋",
            on_success="implementing",
            on_failure="error",
        ),
        WorkflowPhase(
            name="implementing",
            description="Executes tasks from ENGINEERING_PLAN.md",
            icon="🔨",
            on_success="verifying",
            on_failure="error",
        ),
        WorkflowPhase(
            name="verifying",
            description="Runs verification checklist from BEST_PRACTICES.md",
            icon="✅",
            on_success="brainstorming",
            on_failure="error",
        ),
        WorkflowPhase(
            name="brainstorming",
            description="Updates ROADMAP.md with new ideas",
            icon="💡",
            on_success="committing",
            on_failure="committing",  # Brainstorming failures don't block
        ),
        WorkflowPhase(
            name="committing",
            description="Commits changes to git",
            icon="📝",
            on_success="reviewing",
            on_failure="error",
        ),
        WorkflowPhase(
            name="reviewing",
            description=(
                "Automated PR review with code quality checks and BEST_PRACTICES verification"
            ),
            icon="🔍",
            on_success="planning",  # Loop back for next feature
            on_failure="error",
            timeout=900,  # 15 minutes max for review
            max_retries=2,
            retry_delay=30.0,
        ),
    ],
)


def get_workflow(name: str, custom_workflows: dict[str, dict] | None = None) -> WorkflowDefinition:
    """Get a workflow by name.

    Args:
        name: Workflow name ('default' for built-in, or custom name)
        custom_workflows: Dict of custom workflow definitions from workspace

    Returns:
        The workflow definition.

    Raises:
        KeyError: If workflow not found.
    """
    if name == "default":
        return DEFAULT_WORKFLOW

    if custom_workflows and name in custom_workflows:
        return WorkflowDefinition.model_validate(custom_workflows[name])

    raise KeyError(f"Unknown workflow: {name}")


def list_workflows(custom_workflows: dict[str, dict] | None = None) -> list[str]:
    """List all available workflow names.

    Args:
        custom_workflows: Dict of custom workflow definitions from workspace

    Returns:
        List of workflow names (default + custom).
    """
    names = ["default"]
    if custom_workflows:
        names.extend(custom_workflows.keys())
    return names
