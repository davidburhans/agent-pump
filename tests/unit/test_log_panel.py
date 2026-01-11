from pathlib import Path

from agent_pump.tui.widgets.log_panel import LogPanel


def test_log_panel_filtering():
    """Test that LogPanel correctly filters logs based on project path."""
    panel = LogPanel()

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

def test_log_panel_formatting():
    """Test log message formatting."""
    panel = LogPanel()
    panel.write("Normal message")
    assert "Normal message" in panel.text

    panel.write("[ERROR] Something bad")
    assert "**[ERROR] Something bad**" in panel.text

    panel.write("Starting phase")
    assert "### Starting phase" in panel.text
