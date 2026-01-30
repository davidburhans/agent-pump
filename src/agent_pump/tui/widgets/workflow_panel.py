"""Workflow panel widget for displaying workflow diagrams."""

import logging

from textual.containers import Center, Middle, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.orchestrator.workflow_definition import WorkflowPhase

logger = logging.getLogger(__name__)


class WorkflowNodeClicked(Message):
    """Emitted when a workflow node is clicked."""

    def __init__(self, node_name: str) -> None:
        self.node_name = node_name
        super().__init__()


class WorkflowNode(Static):
    """A single node in the workflow visualization."""

    DEFAULT_CSS = """
    WorkflowNode {
        width: auto;
        height: auto;
        min-width: 14;
        padding: 1 2;
        border: solid $surface-lighten-2;
        margin: 1 0;
        text-align: center;
        background: $surface;
        color: $text-muted;
    }

    WorkflowNode.active {
        border: solid $primary;
        color: $text;
        background: $surface-lighten-1;
        text-style: bold;
    }

    WorkflowNode.completed {
        border: solid $success;
        color: $success;
    }

    WorkflowNode.error {
        border: solid $error;
        color: $error;
    }

    WorkflowNode.pulse {
        background: $primary-darken-2;
        border: solid $accent;
        color: $text;
    }

    WorkflowNode:hover {
        background: $surface-lighten-2;
    }
    """

    def __init__(self, phase: WorkflowPhase | str, **kwargs):
        """Initialize the node."""
        super().__init__(**kwargs)
        if isinstance(phase, str):
            self.node_name = phase
            self.icon = "●"
            self.label = phase.title()
        else:
            self.node_name = phase.name
            self.icon = phase.icon or "●"
            self.label = phase.name.title()

        # Idle/Completed/Error nodes might need custom labels/icons
        if self.node_name == "idle":
            self.icon = "⏹"
            self.label = "Idle"
        elif self.node_name == "completed":
            self.icon = "🏁"
            self.label = "Done"
        elif self.node_name == "error":
            self.icon = "❌"
            self.label = "Error"

        self.update(f"{self.icon} {self.label}")

    def on_click(self) -> None:
        """Handle click event."""
        self.post_message(WorkflowNodeClicked(self.node_name))


class WorkflowConnector(Static):
    """Connector arrow between nodes."""

    DEFAULT_CSS = """
    WorkflowConnector {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        height: 1;
    }

    WorkflowConnector.completed {
        color: $success;
        text-style: bold;
    }

    WorkflowConnector.active {
        color: $primary;
        text-style: bold;
    }
    """

    def render(self) -> str:
        return "↓"


class WorkflowPanel(Middle):
    """Component to display the workflow state diagram."""

    DEFAULT_CSS = """
    WorkflowPanel {
        width: 100%;
        height: 1fr;
        border: solid $primary;
        padding: 1;
        background: $surface;
        overflow-y: auto;
    }

    #workflow-nodes {
        width: 100%;
        height: auto;
        align: center top;
    }
    """

    workflow: reactive[ProjectWorkflow | None] = reactive(None)

    def __init__(self, **kwargs):
        """Initialize the workflow panel."""
        super().__init__(**kwargs)
        self.nodes: dict[str, WorkflowNode] = {}
        self.connectors: list[WorkflowConnector] = []
        self.timer = None

    async def watch_workflow(
        self, old_workflow: ProjectWorkflow | None, new_workflow: ProjectWorkflow | None
    ) -> None:
        """Rebuild diagram when workflow changes."""
        await self.rebuild_diagram()

    def set_workflow(self, workflow: ProjectWorkflow | None) -> None:
        """Set the workflow to display (helper for app.py)."""
        if self.workflow != workflow:
            self.workflow = workflow
        else:
            self.refresh_visuals()

    async def rebuild_diagram(self) -> None:
        """Rebuild the node structure."""
        await self.remove_children()
        self.nodes.clear()
        self.connectors.clear()

        if self.timer:
            self.timer.stop()
            self.timer = None

        if not self.workflow:
            await self.mount(Static("No active project selected", id="workflow-nodes"))
            return

        # Build nodes list
        widgets = []

        # Add Idle state
        idle_node = WorkflowNode("idle", id="node-idle")
        widgets.append(idle_node)
        self.nodes["idle"] = idle_node

        c = WorkflowConnector()
        widgets.append(c)
        self.connectors.append(c)

        # Add phases
        phases = self.workflow.workflow_def.phases
        for i, phase in enumerate(phases):
            node = WorkflowNode(phase, id=f"node-{phase.name}")
            widgets.append(node)
            self.nodes[phase.name] = node

            if i < len(phases) - 1:
                c = WorkflowConnector()
                widgets.append(c)
                self.connectors.append(c)

        # Connector to completed
        c = WorkflowConnector()
        widgets.append(c)
        self.connectors.append(c)

        completed_node = WorkflowNode("completed", id="node-completed")
        widgets.append(completed_node)
        self.nodes["completed"] = completed_node

        nodes_container = Vertical(*widgets, id="workflow-nodes")
        await self.mount(nodes_container)

        # Start pulse timer
        self.timer = self.set_interval(0.8, self.pulse_active_node)

        self.refresh_visuals()

    def refresh_visuals(self) -> None:
        """Update node styles based on current state."""
        if not self.workflow:
            return

        current_state = self.workflow.state

        # Reset all nodes
        for node in self.nodes.values():
            node.remove_class("active")
            node.remove_class("completed")
            node.remove_class("error")
            node.remove_class("pulse")

        # Reset connectors
        for conn in self.connectors:
            conn.remove_class("active")
            conn.remove_class("completed")

        # Highlight logic
        phases = [p.name for p in self.workflow.workflow_def.phases]

        # Build ordered list of states for linear visualization: idle -> phases -> completed
        ordered_states = ["idle"] + phases + ["completed"]

        # Determine index of current state in this linear view
        current_idx = -1
        if current_state in ordered_states:
            current_idx = ordered_states.index(current_state)

        # If active state is NOT in the linear path (e.g. error, or unknown),
        # we might just highlight specific nodes or error state.
        # But 'error' is not in our ordered list yet.
        # If error, we might want to highlight the phase that failed?
        # For now, if 'error', let's assume we show the last successful state?
        # Or just don't highlight progress beyond what's done.

        # If state is 'error', we assume the workflow stopped.
        # We can't easily visualize "where" it failed without extra info.
        # But usually state remains in the phase where it failed, OR it transitions to 'error'.
        # If it transitions to 'error', we lose the "phase".
        # Assuming 'current_state' is exactly what's in the workflow object.

        # Mark nodes and connectors
        for i, state_name in enumerate(ordered_states):
            node = self.nodes.get(state_name)
            if not node:
                continue

            if current_idx > i:
                node.add_class("completed")
                # Also highlight connector AFTER this node, if it exists
                if i < len(self.connectors):
                    self.connectors[i].add_class("completed")

            elif current_idx == i:
                node.add_class("active")
                # Connector leading TO this node is completed (handled by previous loop iteration)
                # But connector LEADING FROM this node might be "active" (pulsing)?
                # Or just standard. Let's make it standard.

        # Handle Error state specifically if current_state is 'error'
        if current_state == "error":
             # Maybe highlight the last active node as error?
             # Since we don't know which one, we might just not highlight any specific 'active'
             # and rely on the log.
             # OR if there is an explicit 'error' node, show it.
             # We didn't add an explicit Error node to the linear graph because it's non-linear.
             pass

    def pulse_active_node(self) -> None:
        """Toggle pulse class on active node."""
        if not self.workflow:
            return

        current_state = self.workflow.state

        # Check if running - if not, ensure no pulse
        if not self.workflow.is_running():
            if current_state in self.nodes:
                self.nodes[current_state].remove_class("pulse")
            return

        # Only pulse if it's a phase (not idle/completed/error)
        is_phase = any(p.name == current_state for p in self.workflow.workflow_def.phases)

        if is_phase and current_state in self.nodes:
            self.nodes[current_state].toggle_class("pulse")
