"""Workflow panel widget for displaying workflow diagrams."""

import logging

from textual.containers import Center, Middle, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from agent_pump.models.workflow_snapshot import WorkflowSnapshot, NodeSnapshot
from agent_pump.orchestrator.workflow import ProjectWorkflow

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
        margin: 1;
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
    
    # Accessible name attribute for screen readers
    accessible_name: str | None

    def __init__(self, snapshot: NodeSnapshot, **kwargs):
        """Initialize the node from a snapshot."""
        super().__init__(**kwargs)
        self.node_id = snapshot.id
        self.icon = snapshot.icon
        self.label = snapshot.label
        self.status = snapshot.status
        self.is_active = snapshot.is_active

        self.update(f"{self.icon} {self.label}")
        
        # Apply initial status styles
        if self.status == "active":
            self.add_class("active")
        elif self.status == "completed":
            self.add_class("completed")
        elif self.status == "error":
            self.add_class("error")
            
        # Enable focus for keyboard navigation
        self.can_focus = True
        
        # Initial accessible name
        self.accessible_name = f"{self.label} Phase: {self.status.title()}"

    def on_click(self) -> None:
        """Handle click event."""
        self.post_message(WorkflowNodeClicked(self.node_id))


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

    # We keep 'workflow' reactive for backward compat with app.py setting it,
    # but internally we drive from snapshot.
    workflow: reactive[ProjectWorkflow | None] = reactive(None)
    snapshot: reactive[WorkflowSnapshot | None] = reactive(None)

    def __init__(self, **kwargs):
        """Initialize the workflow panel."""
        super().__init__(**kwargs)
        self.nodes: dict[str, WorkflowNode] = {}
        self.connectors: list[WorkflowConnector] = []
        self.timer = None

    async def watch_workflow(
        self, old_workflow: ProjectWorkflow | None, new_workflow: ProjectWorkflow | None
    ) -> None:
        """Update snapshot when workflow object changes."""
        if new_workflow:
            self.snapshot = new_workflow.get_snapshot()
        else:
            self.snapshot = None

    async def watch_snapshot(
        self, old_snapshot: WorkflowSnapshot | None, new_snapshot: WorkflowSnapshot | None
    ) -> None:
        """Rebuild diagram when snapshot changes."""
        await self.rebuild_diagram()

    def set_workflow(self, workflow: ProjectWorkflow | None) -> None:
        """Set the workflow to display (helper for app.py)."""
        if self.workflow != workflow:
            self.workflow = workflow
        elif workflow:
            # If same workflow object but state changed, force snapshot update
            self.snapshot = workflow.get_snapshot()
        else:
            self.snapshot = None

    def set_snapshot(self, snapshot: WorkflowSnapshot | None) -> None:
        """Directly set the snapshot to display."""
        self.snapshot = snapshot

    async def rebuild_diagram(self) -> None:
        """Rebuild the node structure based on snapshot."""
        await self.remove_children()
        self.nodes.clear()
        self.connectors.clear()

        if self.timer:
            self.timer.stop()
            self.timer = None

        if not self.snapshot:
            await self.mount(Static("No active project selected", id="workflow-nodes"))
            return

        # Build nodes list
        widgets = []
        
        # Iterate through nodes in snapshot
        for i, node_data in enumerate(self.snapshot.nodes):
            node = WorkflowNode(node_data, id=f"node-{node_data.id}")
            widgets.append(Center(node))
            self.nodes[node_data.id] = node

            # Check for edge to next node
            # We assume edges are sequential for vertical layout
            # Logic: If there is an edge starting from this node, add a connector.
            # Find edge where source == node_data.id
            edge = next((e for e in self.snapshot.edges if e.source == node_data.id), None)
            
            if edge:
                c = WorkflowConnector()
                if edge.active:
                    # If edge is active, usually means source is completed
                    c.add_class("completed")
                widgets.append(c)
                self.connectors.append(c)

        nodes_container = Vertical(*widgets, id="workflow-nodes")
        await self.mount(nodes_container)

        # Start pulse timer
        self.timer = self.set_interval(0.8, self.pulse_active_node)

    def pulse_active_node(self) -> None:
        """Toggle pulse class on active node."""
        if not self.snapshot:
            return

        # Find active node
        active_node_id = None
        for node in self.snapshot.nodes:
            if node.is_active:
                active_node_id = node.id
                break
        
        # Check if running - if paused/error, maybe don't pulse?
        # Snapshot doesn't explicitly have "is_running", but we can infer from state or
        # passed workflow. For now, if active, pulse.
        # Maybe check if state is "paused" or "error"?
        if self.snapshot.current_state in ["paused", "error", "completed", "idle"]:
             # Don't pulse
             if active_node_id and active_node_id in self.nodes:
                 self.nodes[active_node_id].remove_class("pulse")
             return

        if active_node_id and active_node_id in self.nodes:
            self.nodes[active_node_id].toggle_class("pulse")
