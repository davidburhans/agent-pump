"""Tests for the CLI chat command."""

from unittest.mock import patch

from click.testing import CliRunner

from agent_pump.cli import main


def test_ask_command_help():
    """Test that the ask command help works."""
    runner = CliRunner()
    result = runner.invoke(main, ["ask", "--help"])
    assert result.exit_code == 0
    assert "Ask a question" in result.output


def test_ask_command_execution():
    """Test executing the ask command."""
    runner = CliRunner()

    with patch("agent_pump.services.chat_service.ChatService") as mock_service_cls:
        mock_instance = mock_service_cls.return_value

        # Setup async generator
        async def mock_stream(*args, **kwargs):
            yield "Response Content"

        mock_instance.chat_stream = mock_stream

        # We need to make sure we don't actually try to init EventBus if it does complex stuff
        with patch("agent_pump.events.bus.EventBus"):
            with patch("agent_pump.cli.Console.print"):
                # Note: we can't easily capture output if we mock console.print
                # but CliRunner captures stdout/stderr.
                # The command uses global `console`.
                pass

            # Run command
            result = runner.invoke(main, ["ask", "My Query", "."])

            assert result.exit_code == 0
            # Verify output captured by runner (Rich console prints to stdout)
            assert "Chatting with project" in result.output
            assert "Response Content" in result.output
