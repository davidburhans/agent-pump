
from agent_pump.models.mcp_config import MCPServerConfig


def test_mcp_server_config_stdio():
    config = MCPServerConfig(
        name="test-server", type="stdio", command="python", args=["script.py"], env={"TEST": "1"}
    )
    assert config.name == "test-server"
    assert config.type == "stdio"
    assert config.command == "python"
    assert config.args == ["script.py"]
    assert config.env == {"TEST": "1"}
    assert not config.disabled


def test_mcp_server_config_sse():
    config = MCPServerConfig(name="sse-server", type="sse", url="http://localhost:8000/sse")
    assert config.name == "sse-server"
    assert config.type == "sse"
    assert config.url == "http://localhost:8000/sse"
    assert not config.disabled


def test_mcp_server_config_disabled():
    config = MCPServerConfig(name="disabled-server", type="stdio", disabled=True)
    assert config.disabled
