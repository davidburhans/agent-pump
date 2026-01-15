"""Modal for reordering roadmap items."""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, ListItem, ListView, Static

from agent_pump.utils.roadmap import RoadmapFeature, RoadmapParser


class RoadmapItem(ListItem):
    """A single item in the roadmap list."""

    def __init__(self, feature: RoadmapFeature):
        super().__init__()
        self.feature = feature

    def compose(self) -> ComposeResult:
        priority_label = f"[{self.feature.priority}] " if self.feature.priority else ""
        yield Label(f"{self.feature.status} {priority_label}{self.feature.title}")


class RoadmapModal(ModalScreen[list[RoadmapFeature] | None]):
    """A modal for prioritizing roadmap items."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("k", "move_up", "Move Up", show=False),
        Binding("j", "move_down", "Move Down", show=False),
        Binding("up", "move_up", "Move Up", show=False),
        Binding("down", "move_down", "Move Down", show=False),
        Binding("K", "move_up", "Move Up"),
        Binding("J", "move_down", "Move Down"),
        Binding("enter", "save", "Save"),
    ]

    DEFAULT_CSS = """
    RoadmapModal {
        align: center middle;
    }

    #roadmap-container {
        width: 80;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #roadmap-list {
        margin: 1 0;
        border: solid $primary-background;
        height: 1fr;
    }

    .help-text {
        color: $text-muted;
        margin-bottom: 1;
    }

    .button-row {
        height: auto;
        align: right middle;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, roadmap_path: Path):
        super().__init__()
        self.roadmap_path = roadmap_path
        self.parser = RoadmapParser(roadmap_path)
        self.features = self.parser.parse()
        self.uncompleted_features = self.parser.get_uncompleted_features()

    def compose(self) -> ComposeResult:
        with Vertical(id="roadmap-container"):
            yield Label("Feature Prioritization", classes="section-title")
            yield Static(
                "Use J/K or Shift+Up/Down to move items. Enter to save, Esc to cancel.",
                classes="help-text",
            )

            items = [RoadmapItem(f) for f in self.uncompleted_features]
            yield ListView(*items, id="roadmap-list")

            yield Horizontal(
                Button("Cancel", id="btn-cancel"),
                Button("Save", variant="success", id="btn-save"),
                classes="button-row",
            )

    def action_move_up(self) -> None:
        """Move selected item up."""
        list_view = self.query_one("#roadmap-list", ListView)
        if list_view.index is not None and list_view.index > 0:
            index = list_view.index
            # Swap in our local list
            item = self.uncompleted_features.pop(index)
            self.uncompleted_features.insert(index - 1, item)

            # Rebuild UI list (Textual's ListView doesn't support easy reordering of widgets)
            self._refresh_list(index - 1)

    def action_move_down(self) -> None:
        """Move selected item down."""
        list_view = self.query_one("#roadmap-list", ListView)
        if list_view.index is not None and list_view.index < len(self.uncompleted_features) - 1:
            index = list_view.index
            # Swap in our local list
            item = self.uncompleted_features.pop(index)
            self.uncompleted_features.insert(index + 1, item)

            # Rebuild UI list
            self._refresh_list(index + 1)

    def _refresh_list(self, new_index: int) -> None:
        """Refresh the ListView content."""
        list_view = self.query_one("#roadmap-list", ListView)
        list_view.clear()
        for f in self.uncompleted_features:
            list_view.append(RoadmapItem(f))
        list_view.index = new_index

    def action_save(self) -> None:
        """Save the new order and dismiss."""
        self.parser.save_with_order(self.uncompleted_features)
        self.dismiss(self.uncompleted_features)

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()
