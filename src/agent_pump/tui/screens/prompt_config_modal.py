import os
import platform
import subprocess

import click
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, Static

from agent_pump.models.workspace import ProjectConfig, Workspace


class PromptConfigModal(ModalScreen[None]):
    """Modal that explains how to configure prompts via files."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    PromptConfigModal {
        align: center middle;
    }

    #modal-container {
        width: 80%;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        layout: vertical;
    }

    #modal-title {
        text-align: center;
        width: 100%;
        margin-bottom: 1;
        text-style: bold;
        background: $primary;
    }

    VerticalScroll {
        height: 1fr;
        scrollbar-size: 1 1;
        border: solid $secondary;
        background: $surface;
    }

    Markdown {
        padding: 1;
    }

    .path-label {
        background: $surface-darken-1;
        padding: 1;
        margin: 1 0;
        text-align: center;
        color: $accent;
        text-style: bold;
    }

    .button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
        dock: bottom;
    }

    .button-row Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        project_config: ProjectConfig,
        workspace: Workspace,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        initial_phase: str | None = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.project_config = project_config
        self.workspace = workspace

    def compose(self) -> ComposeResult:
        """Compose the modal's widgets."""

        states_dir = self.project_config.path / ".agent-pump" / "states"

        doc_content = """
## File-Based Prompt System

You can customize the agent's behavior by editing Markdown files in your project.

### 1. Phase Prompts
Edit the files in `.agent-pump/states/` to replace the default prompts for any phase.

*   `planning.md`
*   `implementing.md`
*   `verifying.md`

**Template Variables:**
*   `{ branch }`: Current git branch name

**Reference Files via `read_file`:**
You can read any file in your project:
*   `{ read_file("ROADMAP.md") }`
*   `{ read_file("ENGINEERING_PLAN.md") }`
*   `{ read_file("docs/api-spec.md") }`

### 2. Pre/Post Hooks
You can prepend or append text to any phase by creating these files in `states/`:
*   `pre-planning.md`: Added *before* the planning prompt.
*   `post-implementing.md`: Added *after* the implementation prompt.

> **Note**: Pre/Post hooks do **not** support template variables currently. They are appended raw.

### 3. Backend-Specific Hooks
You can also add hooks that only apply when using a specific AI backend (e.g., Gemini or Claude).
Create a `backends/` folder in `.agent-pump/` and add:

*   `pre-gemini.md` / `post-gemini.md`
*   `pre-claude.md` / `post-claude.md`

**Prompt Assembly Order:**
1. `pre-<phase>.md`
2. `pre-<backend>.md`
3. Phase Prompt (e.g., `planning.md` with variables filled)
4. `post-<backend>.md`
5. `post-<phase>.md`
"""

        with Container(id="modal-container"):
            yield Static("📝 Prompt Configuration", id="modal-title")

            with VerticalScroll():
                yield Markdown(doc_content)

                yield Static("Prompt Directory:", classes="path-label")
                yield Static(str(states_dir), classes="path-label")

            yield Container(
                Button("Open Directory", variant="primary", id="btn-open"),
                Button("Close (Esc)", variant="default", id="btn-cancel"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-open":
            self.action_open_directory()

    def action_cancel(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)

    def action_open_directory(self) -> None:
        """Open the states directory in the system file explorer."""
        states_dir = self.project_config.path / ".agent-pump" / "states"
        if not states_dir.exists():
            # Fallback to project root if .agent-pump doesn't exist yet
            states_dir = self.project_config.path

        path_str = str(states_dir)

        try:
            if platform.system() == "Windows":
                os.startfile(path_str)  # type: ignore
            elif platform.system() == "Darwin":
                subprocess.run(["open", path_str], check=True)
            else:
                # Linux/Unix
                subprocess.run(["xdg-open", path_str], check=True)

            self.notify(f"Opened {states_dir}", severity="information")
            self.dismiss(None)
        except Exception as e:
            self.notify(
                f"Failed to open directory directly: {e}. Trying fallback...", severity="warning"
            )
            try:
                click.launch(path_str)
                self.dismiss(None)
            except Exception as e2:
                self.notify(f"Fallback failed: {e2}", severity="error")
