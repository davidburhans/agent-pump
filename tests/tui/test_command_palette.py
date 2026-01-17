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

        # Let's just assert that we can find "Toggle Dark Mode" in the results if we implement it.
        # For now, let's see what is there for "Dark".

        input_widget.value = "Dark"

        # Wait for results with a timeout
        async def wait_for_results():
            for _ in range(20):
                await asyncio.sleep(0.1)
                if option_list.option_count > 0:
                    # check if it is the "No matches found" placeholder
                    # Textual might implement this differently, but based on the print output,
                    # we can check the prompt content.
                    first_option = option_list.get_option_at_index(0)
                    prompt_str = str(first_option.prompt)
                    if "No matches found" in prompt_str:
                        return False
                    return True
            return False

        assert await wait_for_results(), "Should find 'Dark' command"

        # Check "Toggle Dark Mode"
        input_widget.value = "Toggle Dark Mode"

        # This is expected to fail until we implement the provider
        # But we assert it for the future
        found = await wait_for_results()
        assert found, "Should find 'Toggle Dark Mode' command"

        # Check "Add Project"
        input_widget.value = "Add Project"
        assert await wait_for_results(), "Should find 'Add Project' command"
