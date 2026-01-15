"""Workflow panel widget for displaying workflow diagrams."""

import logging
from typing import ClassVar

from textual.containers import Center, Horizontal, Middle
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
        margin: 0 1;
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
        border: solid $primary-lighten-1;
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
            self.label = "Completed"
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
        width: 3;
        content-align: center middle;
        color: $text-muted;
        height: 3; 
    }
    """

    def render(self) -> str:
        return " → "


class WorkflowPanel(Middle):
    """Component to display the workflow state diagram."""

    DEFAULT_CSS = """
    WorkflowPanel {
        width: 100%;
        height: 100%;
        border: solid $primary;
        padding: 1;
        background: $surface;
        align: center middle; 
    }

    WorkflowPanel > Center {
        width: auto;
        height: auto;
    }
    """

    def __init__(self, **kwargs):
        """Initialize the workflow panel."""
        super().__init__(**kwargs)
        self.workflow: ProjectWorkflow | None = None
        self.nodes: dict[str, WorkflowNode] = {}
        self.timer = None

    def set_workflow(self, workflow: ProjectWorkflow | None) -> None:
        """Set the workflow to display."""
        logger.debug(f"WorkflowPanel.set_workflow called with: {workflow}")

        # Only rebuild if workflow object changed (or first time)
        # Note: We rely on refresh_visuals for state updates
        is_new_workflow = self.workflow != workflow
        self.workflow = workflow

        if is_new_workflow:
            self.rebuild_diagram()
        else:
            self.refresh_visuals()

    def rebuild_diagram(self) -> None:
        """Rebuild the node structure."""
        self.query("Center").remove()
        self.nodes.clear()

        if self.timer:
            self.timer.stop()
            self.timer = None

        if not self.workflow:
            self.mount(Center(Static("No active project selected")))
            return

        # Build nodes list
        # Build nodes list
        widgets = []

        # Add Idle state
        idle_node = WorkflowNode("idle", id="node-idle")
        widgets.append(idle_node)
        self.nodes["idle"] = idle_node

        widgets.append(WorkflowConnector())

        # Add phases
        phases = self.workflow.workflow_def.phases
        for i, phase in enumerate(phases):
            node = WorkflowNode(phase, id=f"node-{phase.name}")
            widgets.append(node)
            self.nodes[phase.name] = node

            if i < len(phases) - 1:
                widgets.append(WorkflowConnector())

        # Logic for terminal states?
        # Usually completed/error are outcomes.
        # But for linear graph, maybe just show phases?
        # The plan says "WorkflowNode (idle) ... (planning) ... (implementing) ..."
        # What about 'completed' and 'error'?
        # If the state IS completed, we should probably highlight the last node or show a completed node?
        # Let's add 'completed' and 'error' nodes at the end/bottom? or just change state of current nodes?
        # Actually, adding "Completed" node at end is good.

        widgets.append(WorkflowConnector())
        completed_node = WorkflowNode("completed", id="node-completed")
        widgets.append(completed_node)
        self.nodes["completed"] = completed_node

        # Error state usually jumps from anywhere, hard to visualize linearly.
        # Maybe display it separately if active?
        # For now, let's keep it simple. If state is error, we highlight the node that failed?
        # Or we can add an Error node. Let's add it.
        # But where? Maybe not in the linear flow.

        nodes_container = Horizontal(*widgets)
        self.mount(Center(nodes_container))

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

        # Highlight logic
        # If in a phase, everything before it is "completed"
        # If IDLE, nothing is completed.
        # If COMPLETED, everything is completed.

        phases = [p.name for p in self.workflow.workflow_def.phases]

        # Determine index of current state
        current_idx = -1
        if current_state in phases:
            current_idx = phases.index(current_state)
        elif current_state == "completed":
            current_idx = len(phases) # All phases done
        elif current_state == "idle":
            current_idx = -1

        # Mark previous phases as completed
        # Handle 'idle' node
        if current_state != "idle":
            self.nodes["idle"].add_class("completed")
        else:
            self.nodes["idle"].add_class("active")

        # Handle phases
        for i, phase_name in enumerate(phases):
            node = self.nodes.get(phase_name)
            if not node: continue

            if i < current_idx:
                node.add_class("completed")
            elif i == current_idx:
                node.add_class("active")

        # Handle completed/error state specifically
        if current_state == "completed":
            self.nodes["completed"].add_class("completed")
            # Also mark it active/pulsing? Usually completed is static success.
            # But the last phase should be completed too.

        if current_state == "error":
            # Finding where we failed is tricky without history, but usually we just show Error state active
            # Or we can look at workflow.workflow_state.previous_state? (not exposed easily)
            # Maybe just highlight the error node if we added one?
            # I didn't add error node to the container above.
            pass

    def pulse_active_node(self) -> None:
        """Toggle pulse class on active node."""
        if not self.workflow:
            return

        current_state = self.workflow.state
        # Only pulse if it's a phase (not idle/completed/error)
        is_phase = any(p.name == current_state for p in self.workflow.workflow_def.phases)

        if is_phase and current_state in self.nodes:
            self.nodes[current_state].toggle_class("pulse")
