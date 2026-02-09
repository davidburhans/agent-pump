import asyncio
import os
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from agent_pump.cli import main

def test_web_server_startup_generates_key():
    runner = CliRunner()

    async def mock_serve_func(*args, **kwargs):
        return

    # Mock uvicorn to avoid actual server start
    with patch("uvicorn.Server.serve", side_effect=mock_serve_func):
        # Ensure no env var
        with patch.dict(os.environ, {}, clear=True):
            result = runner.invoke(main, ["--web", "--web-port", "8001"])

            # Check output for generated key
            assert "WARNING: No API key provided" in result.output
            assert "Generated temporary key" in result.output
            assert "API Key:" in result.output

def test_web_server_startup_uses_env_key():
    runner = CliRunner()

    async def mock_serve_func(*args, **kwargs):
        return

    # Mock uvicorn
    with patch("uvicorn.Server.serve", side_effect=mock_serve_func):
        # Set env var
        with patch.dict(os.environ, {"AGENT_PUMP_API_KEY": "env-key"}, clear=True):
            result = runner.invoke(main, ["--web", "--web-port", "8002"])

            # Should NOT generate key
            assert "WARNING: No API key provided" not in result.output
            assert "Generated temporary key" not in result.output
