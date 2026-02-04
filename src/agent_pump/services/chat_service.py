"""Service for interactive chat with the codebase."""

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from agent_pump.backends import get_backend
from agent_pump.backends.base import AgentBackend
from agent_pump.events.bus import EventBus
from agent_pump.services.base import BaseService
from agent_pump.utils.context_manager import ContextManager

logger = logging.getLogger(__name__)


class ChatService(BaseService):
    """Service for handling chat interactions with the codebase."""

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize the chat service."""
        super().__init__(event_bus)

    async def chat_stream(
        self,
        query: str,
        project_path: Path,
        backend_name: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response from the backend.

        Args:
            query: The user's question or message.
            project_path: Path to the project root.
            backend_name: Optional backend name to use (defaults to 'gemini').
            history: Optional list of previous messages [{'role': 'user', 'content': '...'}, ...].

        Yields:
            Chunks of the response text.
        """
        # 1. Resolve Backend
        # TODO: Get default backend from project config if available
        backend_name = backend_name or "gemini"
        try:
            backend = get_backend(backend_name)
        except Exception as e:
            yield f"Error loading backend '{backend_name}': {e}"
            return

        if not await backend.is_available():
            yield f"Backend '{backend.name}' is not available. Please install it."
            return

        # 2. Prepare Context
        context_manager = ContextManager(project_path)
        # Use a reasonable default for chat (maybe slightly less than full coding limit to be faster?)
        # For now, just use what context manager gives us.
        context_files = context_manager.get_context_files()
        
        context_str = "\\n".join(
            f"File: {f.path}\\n```\\n{f.content}\\n```" 
            for f in context_files
        )

        # 3. Construct Prompt
        # We can eventually move this to a template file
        system_prompt = (
            "You are an expert software engineer assistant. "
            "You are chatting with a developer about the codebase provided below.\\n"
            "Answer their questions accurately based on the context.\\n"
            "If you don't know the answer based on the context, say so.\\n"
            "Be concise but helpful.\\n"
        )

        history_str = ""
        if history:
            for msg in history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                history_str += f"{role.upper()}: {content}\\n\\n"

        full_prompt = (
            f"{system_prompt}\\n\\n"
            f"CONTEXT:\\n{context_str}\\n\\n"
            f"CHAT HISTORY:\\n{history_str}"
            f"USER: {query}\\n"
            f"ASSISTANT:"
        )

        # 4. Stream Response
        # We use backend.run() for now. 
        # Ideally, we should add a specific chat method to backend protocol later.
        async for chunk in backend.run(project_path, full_prompt, verbose=False):
            yield chunk