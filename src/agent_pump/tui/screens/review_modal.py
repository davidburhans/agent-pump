from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Markdown

from agent_pump.models.review import (
    BestPracticeViolationModel,
    IssueModel,
    ReviewAction,
    ReviewReportModel,
    ReviewStatus,
)


class ReviewModal(ModalScreen[list[ReviewAction]]):
    """Modal for interactively reviewing code quality issues."""

    CSS = """
    ReviewModal {
        align: center middle;
    }

    #dialog {
        width: 90%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1;
        layout: grid;
        grid-size: 2 2;
        grid-rows: 1fr auto;
        grid-columns: 60% 40%;
    }

    #issue-list {
        row-span: 1;
        column-span: 1;
        border: solid $secondary;
        height: 100%;
        margin-right: 1;
    }

    #details-panel {
        row-span: 1;
        column-span: 1;
        border: solid $secondary;
        padding: 1;
        height: 100%;
        overflow-y: auto;
    }

    #footer {
        row-span: 1;
        column-span: 2;
        height: auto;
        border-top: solid $secondary;
        padding-top: 1;
        layout: horizontal;
        align-horizontal: right;
    }

    #action-buttons {
        margin-top: 1;
        height: auto;
        align: center middle;
    }

    #action-buttons Button {
        margin: 0 1;
    }

    .hidden {
        display: none;
    }

    #resolution-input {
        display: none;
        margin-top: 1;
    }

    #btn-submit {
        margin-left: 1;
    }
    """

    current_issue: reactive[IssueModel | BestPracticeViolationModel | None] = reactive(None)

    def __init__(self, report: ReviewReportModel):
        super().__init__()
        self.report = report
        self.decisions: dict[str, ReviewAction] = {}  # issue_id -> Action

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield DataTable(id="issue-list")

            with Vertical(id="details-panel"):
                yield Label("Select an issue to view details", id="details-title", classes="bold")
                yield Markdown("", id="details-content")

                with Horizontal(id="action-buttons", classes="hidden"):
                    yield Button("Ignore", id="btn-ignore", variant="warning")
                    yield Button("Auto-Fix", id="btn-autofix", variant="primary")
                    yield Button("Mark Fixed", id="btn-fixed", variant="success")

                yield Input(placeholder="Reason for ignoring...", id="resolution-input")

            with Horizontal(id="footer"):
                yield Label(f"Found {len(self.report.issues)} issues", classes="dim")
                with Container(classes="spacer"):
                    pass
                yield Button("Cancel", id="btn-cancel", variant="error")
                yield Button("Submit Review", id="btn-submit", variant="primary")

    def on_mount(self) -> None:
        table = self.query_one("#issue-list", DataTable)
        table.add_columns("Type", "File", "Message", "Status")
        table.cursor_type = "row"

        # Populate table
        for issue in self.report.issues:
            table.add_row(
                f"[{issue.severity.upper()}]",
                f"{issue.file_path}:{issue.line_number or '?'}",
                issue.message,
                "Pending",
                key=issue.id,
            )

        for violation in self.report.violations:
            table.add_row(
                "[BP]",
                violation.section,
                violation.description,
                "Pending",
                key=violation.id,
            )

        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        issue_id = event.row_key.value
        self._show_issue_details(issue_id)

    def _show_issue_details(self, issue_id: str) -> None:
        # Find the issue
        issue = next((i for i in self.report.issues if i.id == issue_id), None)
        if not issue:
            issue = next((v for v in self.report.violations if v.id == issue_id), None)

        self.current_issue = issue
        if not issue:
            return

        # Update details UI
        title = self.query_one("#details-title", Label)
        content = self.query_one("#details-content", Markdown)
        buttons = self.query_one("#action-buttons")
        buttons.remove_class("hidden")

        # Reset input
        inp = self.query_one("#resolution-input", Input)
        inp.display = False
        inp.value = ""

        # Set content
        if isinstance(issue, IssueModel):
            title.update(f"Issue: {issue.file_path}")
            md = f"""
**Message:** {issue.message}

**Severity:** {issue.severity}

**Location:** {issue.file_path}:{issue.line_number}

**Suggestion:** {issue.suggestion}
"""
        else:
            title.update(f"Violation: {issue.section}")
            md = f"""
**Requirement:** {issue.requirement}

**Description:** {issue.description}

**Location:** {issue.file_path or "General"}
"""
        content.update(md)

        # Disable auto-fix for best practices or critical issues if unimplemented
        autofix_btn = self.query_one("#btn-autofix", Button)
        if isinstance(issue, BestPracticeViolationModel):
            autofix_btn.disabled = True
        else:
            autofix_btn.disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-submit":
            self.dismiss(list(self.decisions.values()))
        elif event.button.id == "btn-cancel":
            self.dismiss([])

        # Issue actions
        elif self.current_issue:
            issue_id = self.current_issue.id
            if event.button.id == "btn-ignore":
                # Show input for reason
                inp = self.query_one("#resolution-input", Input)
                inp.display = True
                inp.focus()
            elif event.button.id == "btn-autofix":
                self._set_decision(issue_id, ReviewStatus.AUTO_FIX)
            elif event.button.id == "btn-fixed":
                self._set_decision(issue_id, ReviewStatus.FIXED)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "resolution-input" and self.current_issue:
            self._set_decision(
                self.current_issue.id,
                ReviewStatus.IGNORED,
                resolution_details=event.value,
            )
            event.input.display = False

    def _set_decision(
        self, issue_id: str, status: ReviewStatus, resolution_details: str | None = None
    ) -> None:
        self.decisions[issue_id] = ReviewAction(
            issue_id=issue_id,
            status=status,
            resolution_details=resolution_details,
        )
        # Update table row status
        table = self.query_one("#issue-list", DataTable)
        try:
            table.update_cell(issue_id, "Status", status.value.title())
        except Exception:
            # Handle case where key might differ or table refreshed
            pass

        self.notify(f"Marked as {status.value}")
