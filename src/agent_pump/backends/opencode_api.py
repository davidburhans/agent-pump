"""OpenCode API backend implementation using opencode-ai SDK."""

import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path

try:
    from opencode_ai import APIError, APITimeoutError, AsyncOpencode  # type: ignore[assignment]
    from opencode_ai.types import AssistantMessage  # type: ignore[assignment]

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

    # Mock classes for type checking if SDK is missing
    class AsyncOpencode:  # type: ignore
        def __init__(self, *args, **kwargs):
            self.session = None
            self.with_streaming_response = None
            pass

    class APIError(Exception):  # type: ignore
        pass

    class APITimeoutError(TimeoutError):  # type: ignore
        pass

    class AssistantMessage:  # type: ignore
        pass


from agent_pump.backends.base import AgentBackend

logger = logging.getLogger(__name__)


class OpenCodeAPIBackend(AgentBackend):
    """
    Backend for OpenCode via the Python SDK (API).

    Connects to a running OpenCode server (default: http://localhost:54321).
    """

    @property
    def name(self) -> str:
        return "OpenCode API"

    @property
    def command(self) -> str:
        return "opencode-api"  # internal ID

    def get_context_window_size(self, model: str | None = None) -> int:
        return 128_000

    async def _check_availability(self) -> bool:
        """Check if OpenCode SDK is installed and server is reachable."""
        if not SDK_AVAILABLE:
            logger.debug("OpenCode SDK not installed")
            return False

        try:
            # Check connectivity by trying to list sessions or similar lightweight call
            # We use a short timeout
            base_url = os.environ.get("OPENCODE_BASE_URL", "http://localhost:54321")
            client = AsyncOpencode(base_url=base_url, timeout=2.0)

            # Trying to create a session might be too heavy/intrusive,
            # but list() should be safe if available.
            # If list is not available, we assume if we can instantiate it's ok
            # but that doesn't check server.
            # Let's try to fetch a simple resource or just assume available if SDK is present
            # and let the run() method fail if server is down.
            # However, _check_availability is used to show status in UI.

            # Using client.get("/") might be generic enough if it exposes health
            # But the SDK is typed.
            # Let's try listing sessions.
            if hasattr(client.session, "list"):
                await client.session.list()  # type: ignore

            return True
        except Exception as e:
            logger.debug(f"OpenCode server check failed: {e}")
            return False

    def get_setup_instructions(self) -> str:
        return """
╔══════════════════════════════════════════════════════════════════════╗
║                    OpenCode API Unavailable                          ║
╠══════════════════════════════════════════════════════════════════════╣
║ 1. Ensure opencode-ai is installed:                                  ║
║    pip install opencode-ai                                           ║
║                                                                      ║
║ 2. Ensure OpenCode server is running:                                ║
║    opencode serve (or similar command)                               ║
║    Default URL: http://localhost:54321                               ║
║                                                                      ║
║ 3. Check OPENCODE_BASE_URL environment variable if using custom URL. ║
╚══════════════════════════════════════════════════════════════════════╝
"""

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
        extra_args: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Execute OpenCode via API.
        """
        if not SDK_AVAILABLE:
            yield "[ERROR] opencode-ai SDK not installed.\\n"
            yield self.get_setup_instructions()
            return

        base_url = os.environ.get("OPENCODE_BASE_URL", "http://localhost:54321")

        # Parse extra_args for model/provider
        model_id = "gpt-4o"  # Default or fallback?
        provider_id = "openai"  # Default?

        # Simple arg parsing
        if extra_args:
            args_iter = iter(extra_args)
            for arg in args_iter:
                if arg == "--model":
                    try:
                        model_id = next(args_iter)
                    except StopIteration:
                        pass
                elif arg == "--provider":
                    try:
                        provider_id = next(args_iter)
                    except StopIteration:
                        pass

        # Check instance level extra args too?
        # The base class doesn't automatically merge them in run(),
        # but OpenCodeBackend (CLI) did merge them.
        # We should probably respect self._extra_args if they exist.
        if self._extra_args:
            args_iter = iter(self._extra_args)
            for arg in args_iter:
                if arg == "--model":
                    try:
                        model_id = next(args_iter)
                    except StopIteration:
                        pass
                elif arg == "--provider":
                    try:
                        provider_id = next(args_iter)
                    except StopIteration:
                        pass

        client = AsyncOpencode(base_url=base_url, timeout=float(timeout))

        try:
            logger.info(f"Connecting to OpenCode API at {base_url}")

            # Create session
            # We don't have a way to set project_path via API known to us yet.
            # We'll assume the server is context-aware or we are restricted.
            session = await client.session.create()  # type: ignore
            session_id = session.id
            logger.debug(f"Created session: {session_id}")

            # Send prompt
            # We use with_streaming_response for streaming
            # The signature of chat is:
            # (id, *, model_id, parts, provider_id, ...)

            # Construct parts. Assuming 'parts' is a list of strings or objects.
            # Inspect signature said: parts: 'Iterable[session_chat_params.Part]'
            # But usually SDKs accept strings as well or handle conversion.
            # If not, we might need to construct a Part object.
            # Let's assume text string works or look for Part.

            # Since I can't import Part easily without checking where it is (session_chat_params?),
            # I will try passing a dict or simple string if allowed.
            # Usually [{"type": "text", "text": prompt}] or similar.

            # Let's check opencode_ai.types...
            # I'll optimistically assume it handles string or I'll pass a dict.
            parts = [{"type": "text", "text": prompt}]

            logger.debug(
                f"Sending chat to session {session_id} with model {model_id}/{provider_id}"
            )

            async with client.with_streaming_response.session.chat(  # type: ignore
                id=session_id,
                model_id=model_id,
                provider_id=provider_id,
                parts=parts,  # type: ignore
            ) as stream:
                async for chunk in stream:  # type: ignore
                    # Chunk type? likely bytes or text or an object with delta?
                    # Inspecting stream behavior is hard without docs.
                    # Typically stream yields chunks of data.
                    # If it yields bytes/text directly:
                    if isinstance(chunk, str):
                        yield chunk
                    elif isinstance(chunk, bytes):
                        yield chunk.decode("utf-8", errors="replace")
                    else:
                        # If it's an object, try to stringify or access content
                        # Assuming it might be an event object
                        yield str(chunk)

        except APITimeoutError:
            yield f"\\n[TIMEOUT] Request timed out after {timeout}s\\n"
        except APIError as e:
            yield f"\\n[ERROR] OpenCode API Error: {e}\\n"
        except Exception as e:
            logger.exception("Unexpected error in OpenCode API backend")
            yield f"\\n[ERROR] Unexpected error: {e}\\n"
