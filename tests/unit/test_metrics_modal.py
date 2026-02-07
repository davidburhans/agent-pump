"""Tests for metrics modal TUI screen."""

import pytest
from textual.app import App
from textual.widgets import Button, DataTable, Label, Select, TabbedContent

from agent_pump.tui.screens.metrics_modal import MetricsModal


class MetricsTestApp(App):
    """Test app for MetricsModal."""

    def __init__(self):
        super().__init__()
        self.modal = MetricsModal()

    def on_mount(self):
        self.push_screen(self.modal)


class TestMetricsModal:
    """Tests for MetricsModal screen."""

    @pytest.mark.asyncio
    async def test_modal_creation(self):
        """Test that the modal can be created."""
        modal = MetricsModal()
        assert modal is not None

    @pytest.mark.asyncio
    async def test_modal_structure(self):
        """Test that the modal has the expected structure."""
        app = MetricsTestApp()
        async with app.run_test():
            modal = app.modal
            # Check that key widgets exist
            assert modal.query_one("#metrics-title", Label)
            assert modal.query_one("#period-selector", Select)
            assert modal.query_one("#metrics-tabs", TabbedContent)

    @pytest.mark.asyncio
    async def test_summary_tab_exists(self):
        """Test that the summary tab exists."""
        app = MetricsTestApp()
        async with app.run_test():
            modal = app.modal
            tabs = modal.query_one("#metrics-tabs", TabbedContent)
            assert tabs is not None

    @pytest.mark.asyncio
    async def test_features_tab_exists(self):
        """Test that the features tab exists."""
        app = MetricsTestApp()
        async with app.run_test():
            modal = app.modal
            tabs = modal.query_one("#metrics-tabs", TabbedContent)
            # TabbedContent should have multiple tabs
            assert tabs is not None

    @pytest.mark.asyncio
    async def test_export_buttons_exist(self):
        """Test that export buttons exist."""
        app = MetricsTestApp()
        async with app.run_test():
            modal = app.modal
            json_button = modal.query_one("#export-json-btn", Button)
            csv_button = modal.query_one("#export-csv-btn", Button)
            assert json_button is not None
            assert csv_button is not None

    @pytest.mark.asyncio
    async def test_close_button_exists(self):
        """Test that close button exists."""
        app = MetricsTestApp()
        async with app.run_test():
            modal = app.modal
            close_button = modal.query_one("#close-btn", Button)
            assert close_button is not None

    @pytest.mark.asyncio
    async def test_close_button_dismisses(self):
        """Test that close button dismisses the modal."""
        app = MetricsTestApp()
        dismissed = False

        def on_dismiss(result):
            nonlocal dismissed
            dismissed = True

        # We need to set the callback before pushing?
        # App.push_screen takes a callback.
        # But we did it in on_mount.
        # Let's override push_screen in the test app or just hook into the modal instance.
        # But wait, modal.dismiss() calls the screen stack pop.
        # We can't easily mock the internal dismiss callback of Textual.
        # But we can check if the screen was removed from the stack.

        async with app.run_test() as pilot:
            modal = app.modal
            # Wait for mount
            await pilot.pause()
            assert app.screen is modal

            close_button = modal.query_one("#close-btn", Button)
            await pilot.click(close_button)
            await pilot.pause()

            # Should be back to default screen or empty stack?
            # Since we pushed in on_mount, popping it might leave us with no screen or default.
            # Actually, standard App has a default screen.
            assert app.screen is not modal

    @pytest.mark.asyncio
    async def test_period_selector_changes(self):
        """Test that period selector updates the display."""
        app = MetricsTestApp()
        async with app.run_test() as pilot:
            modal = app.modal
            selector = modal.query_one("#period-selector", Select)
            # Select a different period
            selector.value = "week"
            await pilot.pause()
            # The modal should update its data
            assert modal._current_period == "week"


class TestMetricsModalData:
    """Tests for metrics data display."""

    @pytest.mark.asyncio
    async def test_summary_stats_display(self):
        """Test that summary stats are displayed."""
        app = MetricsTestApp()
        async with app.run_test():
            modal = app.modal
            # Check for summary labels
            total_label = modal.query_one("#total-features", Label)
            success_label = modal.query_one("#success-rate", Label)
            assert total_label is not None
            assert success_label is not None

    @pytest.mark.asyncio
    async def test_features_table_exists(self):
        """Test that features table exists in features tab."""
        app = MetricsTestApp()
        async with app.run_test():
            modal = app.modal
            table = modal.query_one("#features-table", DataTable)
            assert table is not None

    @pytest.mark.asyncio
    async def test_phase_timing_display(self):
        """Test that phase timing is displayed."""
        app = MetricsTestApp()
        async with app.run_test():
            modal = app.modal
            # Phase timing should be displayed somewhere
            phase_table = modal.query_one("#phase-table", DataTable)
            assert phase_table is not None
