"""MCP Client Manager for connecting to remote servers."""

import logging
import os
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client

from agent_pump.models.mcp_config import MCPServerConfig

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages connections to remote MCP servers."""

    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.sessions: dict[str, ClientSession] = {}

    async def get_session(self, config: MCPServerConfig) -> ClientSession:
        """Get or create a session for the given server config."""
        if config.name in self.sessions:
            # We assume session is still valid if it exists
            return self.sessions[config.name]

        if config.disabled:
            raise ValueError(f"MCP server {config.name} is disabled")

        logger.info(f"Connecting to MCP server: {config.name} ({config.type})")

        try:
            if config.type == "stdio":
                if not config.command:
                    raise ValueError(f"Command required for stdio server {config.name}")

                # Use current environment if not specified, but updated with config.env
                env = os.environ.copy()
                if config.env:
                    env.update(config.env)

                params = StdioServerParameters(
                    command=config.command,
                    args=config.args,
                    env=env,
                )

                # Enter context manager and keep it open
                read, write = await self.exit_stack.enter_async_context(stdio_client(params))
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))

            elif config.type == "sse":
                if not config.url:
                    raise ValueError(f"URL required for sse server {config.name}")

                read, write = await self.exit_stack.enter_async_context(sse_client(config.url))
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))

            else:
                raise ValueError(f"Unknown server type: {config.type}")

            await session.initialize()
            self.sessions[config.name] = session
            logger.info(f"Connected to MCP server: {config.name}")
            return session

        except Exception as e:
            logger.error(f"Failed to connect to MCP server {config.name}: {e}")
            raise

    async def close(self):
        """Close all connections."""
        if self.sessions:
            logger.info(f"Closing {len(self.sessions)} MCP client connections")
            await self.exit_stack.aclose()
            self.sessions.clear()
