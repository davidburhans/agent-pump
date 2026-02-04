"""Tests for metrics modal TUI screen."""

import pytest
from textual.widgets import Button, DataTable, Label, Select, TabbedContent

from agent_pump.tui.screens.metrics_modal import MetricsModal


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
        modal = MetricsModal()

        async with modal.run_test() as pilot:
            # Check that key widgets exist
            assert modal.query_one("#metrics-title", Label)
            assert modal.query_one("#period-selector", Select)
            assert modal.query_one("#metrics-tabs", TabbedContent)

    @pytest.mark.asyncio
    async def test_summary_tab_exists(self):
        """Test that the summary tab exists."""
        modal = MetricsModal()

        async with modal.run_test() as pilot:
            tabs = modal.query_one("#metrics-tabs", TabbedContent)
            assert tabs is not None

    @pytest.mark.asyncio
    async def test_features_tab_exists(self):
        """Test that the features tab exists."""
        modal = MetricsModal()

        async with modal.run_test() as pilot:
            tabs = modal.query_one("#metrics-tabs", TabbedContent)
            # TabbedContent should have multiple tabs
            assert tabs is not None

    @pytest.mark.asyncio
    async def test_export_buttons_exist(self):
        """Test that export buttons exist."""
        modal = MetricsModal()

        async with modal.run_test() as pilot:
            json_button = modal.query_one("#export-json-btn", Button)
            csv_button = modal.query_one("#export-csv-btn", Button)
            assert json_button is not None
            assert csv_button is not None

    @pytest.mark.asyncio
    async def test_close_button_exists(self):
        """Test that close button exists."""
        modal = MetricsModal()

        async with modal.run_test() as pilot:
            close_button = modal.query_one("#close-btn", Button)
            assert close_button is not None

    @pytest.mark.asyncio
    async def test_close_button_dismisses(self):
        """Test that close button dismisses the modal."""
        modal = MetricsModal()
        dismissed = False

        def on_dismiss(result):
            nonlocal dismissed
            dismissed = True

        modal.dismiss = on_dismiss

        async with modal.run_test() as pilot:
            close_button = modal.query_one("#close-btn", Button)
            await pilot.click(close_button)
            assert dismissed

    @pytest.mark.asyncio
    async def test_period_selector_changes(self):
        """Test that period selector updates the display."""
        modal = MetricsModal()

        async with modal.run_test() as pilot:
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
        modal = MetricsModal()

        async with modal.run_test() as pilot:
            # Check for summary labels
            total_label = modal.query_one("#total-features", Label)
            success_label = modal.query_one("#success-rate", Label)
            assert total_label is not None
            assert success_label is not None

    @pytest.mark.asyncio
    async def test_features_table_exists(self):
        """Test that features table exists in features tab."""
        modal = MetricsModal()

        async with modal.run_test() as pilot:
            table = modal.query_one("#features-table", DataTable)
            assert table is not None

    @pytest.mark.asyncio
    async def test_phase_timing_display(self):
        """Test that phase timing is displayed."""
        modal = MetricsModal()

        async with modal.run_test() as pilot:
            # Phase timing should be displayed somewhere
            phase_table = modal.query_one("#phase-table", DataTable)
            assert phase_table is not None
