import asyncio

import pytest

from agent_pump.tui.app import AgentPumpApp


@pytest.mark.asyncio
async def test_command_palette_discovery():
    app = AgentPumpApp()
    async with app.run_test() as pilot:
        # Check if command palette is enabled
        assert app.ENABLE_COMMAND_PALETTE is True, "Command Palette should be enabled"

        # In Textual, we can get available commands via the CommandPalette screen
        # Or better, we can check the CommandPalette class or how App discovers commands.
        # But simply enabling it and checking if it opens might be a start.

        # To test discovery programmatically without opening the UI,
        # we can look at the default command provider.

        # Note: Textual's internal command discovery is async.

        # Let's trigger the command palette
        await pilot.press("ctrl+p")

        # Check if the screen is pushed
        assert type(app.screen).__name__ == "CommandPalette"

        # Now we can query the CommandPalette to see what it found.
        # The CommandPalette widget populates a ListView.
        # However, it might take some time to populate.

        # Actually, let's just inspect the app's `commands` property if it exists,
        # or rely on the fact that we can search.

        from textual.widgets import Input

        palette = app.screen
        input_widget = palette.query_one("Input", Input)

        # Search for "Dark"
        input_widget.value = "Dark"
        await pilot.pause()

        # Wait for the results to populate
        # The command palette runs a worker to populate results.
        # We can try to access the command provider directly or inspect the list view.

        # Let's inspect the `CommandPalette` screen logic.
        # It usually populates an OptionList or ListView.

        # We can simulate typing "Toggle Dark Mode"
        input_widget.value = "Toggle Dark Mode"

        # Give it a moment to process (debounce + search)
        await asyncio.sleep(0.5)

        # In a real TUI test we might need to inspect the children of the screen
        from textual.widgets import OptionList
        option_list = palette.query_one(OptionList)

        # Inspect the content of option list
        # Since this is a unit test, we might not see the exact visual output easily
        # but we can check if there are items.

        # However, to be more robust and check what commands are actually registered:

        # We can manually invoke discovery on the app
        # But `app.get_commands()` is not a public API usually exposed this way?
        # Actually `App.get_possible_commands` might be useful? No.

        # Helper to get result texts
        async def get_results_texts(wait_time=0.2):
            # Wait for search to process
            await asyncio.sleep(wait_time)
            results = []
            if option_list.option_count > 0:
                for i in range(option_list.option_count):
                    opt = option_list.get_option_at_index(i)
                    prompt_str = str(opt.prompt)
                    if "No matches found" in prompt_str:
                        continue
                    results.append(prompt_str)
            return results

        # Helper to verify a command is present
        async def assert_command_present(command_name: str, query: str | None = None):
            if query:
                input_widget.value = query
            else:
                input_widget.value = command_name

            # Retry loop to handle async population
            for _ in range(10):
                results = await get_results_texts()
                # Check if exact match or contains (Textual highlights might add markup, so strictly checking "in" str)
                for res in results:
                    if command_name in res:
                        return
                # If not found, wait a bit more
                await asyncio.sleep(0.1)

            # Final check
            results = await get_results_texts(wait_time=0.5)
            found = any(command_name in res for res in results)
            assert found, f"Command '{command_name}' not found in results: {results}"

        # Helper to verify a command is NOT present
        async def assert_command_missing(command_name: str, query: str | None = None):
            if query:
                input_widget.value = query
            else:
                input_widget.value = command_name

            # Wait for results to stabilize
            results = await get_results_texts(wait_time=0.5)
            found = any(command_name in res for res in results)
            assert not found, f"Command '{command_name}' SHOULD NOT be in results: {results}"


        # Check "Toggle Dark Mode"
        await assert_command_present("Toggle Dark Mode")

        # Check "Add Project"
        await assert_command_present("Add Project")

        # Check "Quit Application"
        await assert_command_present("Quit Application")

        # Check "Toggle Sort Order"
        await assert_command_present("Toggle Sort Order")

        # Verify project-specific commands are NOT present
        # We search for "Remove Project" but assert it is NOT in the results
        await assert_command_missing("Remove Project")

        # Now simulate selecting a project
        from pathlib import Path
        app.selected_project = Path("/tmp/dummy-project")

        # Check "Remove Project" - Force update by clearing input first
        input_widget.value = ""
        await asyncio.sleep(0.1)
        await assert_command_present("Remove Project")

        # Check "Start Selected"
        await assert_command_present("Start Selected")

        # Check "Reset Project"
        await assert_command_present("Reset Project")
