from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from agent_pump.tui.widgets.log_panel import LogPanel


class LogPanelTestApp(App):
    """Harness app for testing LogPanel."""

    def compose(self) -> ComposeResult:
        yield LogPanel(id="log-panel")


@pytest.mark.asyncio
async def test_log_panel_filtering():
    """Test that LogPanel correctly filters logs based on project path."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = pilot.app.query_one(LogPanel)
        path_a = Path("/project/a")
        path_b = Path("/project/b")

        # Write logs
        panel.write("Global log")
        panel.write("Project A log", project_path=path_a)
        panel.write("Project B log", project_path=path_b)

        # Initial state: Filter None -> Should show all
        assert "Global log" in panel.text
        assert "Project A log" in panel.text
        assert "Project B log" in panel.text

        # Filter A
        panel.set_filter(path_a)
        assert "Global log" in panel.text
        assert "Project A log" in panel.text
        assert "Project B log" not in panel.text

        # Filter B
        panel.set_filter(path_b)
        assert "Global log" in panel.text
        assert "Project A log" not in panel.text
        assert "Project B log" in panel.text

        # Filter None (Show All)
        panel.set_filter(None)
        assert "Global log" in panel.text
        assert "Project A log" in panel.text
        assert "Project B log" in panel.text


@pytest.mark.asyncio
async def test_log_panel_formatting():
    """Test log message formatting."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = pilot.app.query_one(LogPanel)
        panel.write("Normal message")
        assert "Normal message" in panel.text

        panel.write("[ERROR] Something bad")
        assert "**[ERROR] Something bad**" in panel.text

        panel.write("Starting phase")
        assert "### Starting phase" in panel.text


@pytest.mark.asyncio
async def test_log_panel_sorting():
    """Test log sorting."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = pilot.app.query_one(LogPanel)
        # Default is desc (newest first)
        assert panel.sort_order == "desc"

        panel.write("Msg 1")
        panel.write("Msg 2")

        # In DESC, Msg 2 (newest) should appear before Msg 1 in the text
        idx1 = panel.text.find("Msg 1")
        idx2 = panel.text.find("Msg 2")
        assert idx2 < idx1

        # Toggle to ASC
        panel.toggle_sort()
        assert panel.sort_order == "asc"

        # In ASC, Msg 1 (oldest) should appear before Msg 2
        idx1 = panel.text.find("Msg 1")
        idx2 = panel.text.find("Msg 2")
        assert idx1 < idx2


@pytest.mark.asyncio
async def test_log_panel_state_filtering():
    """Test filtering by state."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = pilot.app.query_one(LogPanel)
        panel.write("Planning log", state="planning")
        panel.write("Implementing log", state="implementing")

        # Filter planning only
        panel.set_filter(None, states=["planning"])
        assert "Planning log" in panel.text
        assert "Implementing log" not in panel.text

        # Filter both
        panel.set_filter(None, states=["planning", "implementing"])
        assert "Planning log" in panel.text
        assert "Implementing log" in panel.text


@pytest.mark.asyncio
async def test_log_panel_task_filtering():
    """Test filtering by task name."""
    app = LogPanelTestApp()
    async with app.run_test() as pilot:
        panel = pilot.app.query_one(LogPanel)
        panel.write("Task A log", task="Feature A")
        panel.write("Task B log", task="Feature B")

        panel.set_filter(None, task="Feature A")
        assert "Task A log" in panel.text
        assert "Task B log" not in panel.text
