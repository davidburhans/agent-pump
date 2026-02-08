import json
from pathlib import Path


def inject_communication_config(
    project_id: str,
    backend_type: str,
    callback_url: str,
    mcp_port: int = 3333,
) -> dict[str, str]:
    """
    Returns environment variables to inject into the backend process.
    Also writes MCP config files for backends that need them.
    """
    env = {
        "AGENT_PUMP_CALLBACK_URL": callback_url,
        "AGENT_PUMP_PROJECT_ID": project_id,
        "AGENT_PUMP_MCP_PORT": str(mcp_port),
    }

    # For Gemini CLI: write to ~/.gemini/settings.json
    if backend_type == "gemini":
        gemini_config = Path.home() / ".gemini" / "settings.json"
        try:
            config = {}
            if gemini_config.exists():
                try:
                    config = json.loads(gemini_config.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass

            config.setdefault("mcpServers", {})
            config["mcpServers"]["agent-pump"] = {"url": f"http://localhost:{mcp_port}/mcp/sse"}

            gemini_config.parent.mkdir(parents=True, exist_ok=True)
            gemini_config.write_text(json.dumps(config, indent=2), encoding="utf-8")
        except Exception:
            # Log or ignore if we can't write config (e.g. permission error)
            # We don't have a logger here easily, so maybe just print/ignore
            pass

    # For Claude: write to ~/.claude/mcp_servers.json
    elif backend_type == "claude":
        claude_config = Path.home() / ".claude" / "mcp_servers.json"
        try:
            config = {}
            if claude_config.exists():
                try:
                    config = json.loads(claude_config.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass

            config["agent-pump"] = {
                "command": "npx",  # or direct connection
                "args": ["-y", "mcp-client", f"http://localhost:{mcp_port}/mcp/sse"],
            }

            claude_config.parent.mkdir(parents=True, exist_ok=True)
            claude_config.write_text(json.dumps(config, indent=2), encoding="utf-8")
        except Exception:
            pass

    return env
