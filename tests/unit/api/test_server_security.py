"""Unit tests for server security configurations."""

import pytest
import os
from agent_pump.api.server import create_server

class TestServerSecurity:
    """Tests for server security configurations."""

    def test_production_mode_requires_api_key(self, monkeypatch):
        """Test that production mode (debug=False) requires an API key."""
        # Ensure no environment variable is set
        monkeypatch.delenv("AGENT_PUMP_API_KEY", raising=False)

        with pytest.raises(RuntimeError) as excinfo:
            create_server(debug=False, api_key=None)

        assert "AGENT_PUMP_API_KEY environment variable must be set" in str(excinfo.value)

    def test_production_mode_accepts_api_key(self):
        """Test that production mode works when API key is provided."""
        app = create_server(debug=False, api_key="test-key")
        assert app.state.api_key == "test-key"

    def test_production_mode_accepts_env_api_key(self, monkeypatch):
        """Test that production mode works when API key is provided via env var."""
        monkeypatch.setenv("AGENT_PUMP_API_KEY", "env-key")
        app = create_server(debug=False, api_key=None)
        assert app.state.api_key == "env-key"

    def test_debug_mode_auto_generates_key(self, monkeypatch):
        """Test that debug mode auto-generates API key if missing."""
        monkeypatch.delenv("AGENT_PUMP_API_KEY", raising=False)

        # This currently generates a file, which is a side effect.
        # Ideally we'd mock the file writing part too, but for now we check the key generation.
        app = create_server(debug=True, api_key=None)
        assert app.state.api_key is not None
        assert len(app.state.api_key) > 0

    def test_debug_mode_accepts_api_key(self):
        """Test that debug mode uses provided API key."""
        app = create_server(debug=True, api_key="debug-key")
        assert app.state.api_key == "debug-key"
