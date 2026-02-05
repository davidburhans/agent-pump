from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.app import App
from textual.widgets import Input, RichLog

from agent_pump.tui.screens.chat_screen import ChatScreen


@pytest.mark.asyncio
async def test_chat_screen_flow():
    project_path = Path("/tmp/test_project")

    class TestApp(App):
        def on_mount(self):
            self.push_screen(ChatScreen(project_path))

    app = TestApp()
    app.event_bus = MagicMock()

    async with app.run_test() as pilot:
        # Wait for screen to be pushed
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, ChatScreen)

        log = screen.query_one(RichLog)
        input_box = screen.query_one(Input)

        # Verify initial state
        assert "Chatting with test_project" in log.lines[0].text

        # Mock ChatService
        with patch("agent_pump.tui.screens.chat_screen.ChatService") as mock_service_cls:
            mock_instance = mock_service_cls.return_value

            async def mock_stream(*args, **kwargs):
                yield "AI Response"
            mock_instance.chat_stream = mock_stream

            # Focus input
            input_box.focus()
            await pilot.pause()
            assert input_box.has_focus

            # Type value
            input_box.value = "Hello AI"

            # Submit
            await pilot.press("enter")

            # Wait for async worker
            await pilot.pause(1.0)

            # Check log
            full_text = "\\n".join([line.text for line in log.lines])

            assert "User: Hello AI" in full_text
            assert "Assistant:" in full_text
            assert "AI Response" in full_text

            # Check input is cleared and enabled
            assert input_box.value == ""
            assert not input_box.disabled
