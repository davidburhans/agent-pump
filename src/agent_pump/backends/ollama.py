"""Ollama backend implementation."""

import json
import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path

import httpx

from agent_pump.backends.base import AgentBackend
from agent_pump.config import Config

logger = logging.getLogger(__name__)


class OllamaBackend(AgentBackend):
    """
    Backend for Ollama (local LLM runner).

    Connects to an Ollama instance via HTTP API.
    Default endpoint: http://localhost:11434
    """

    @property
    def name(self) -> str:
        return "Ollama"

    @property
    def command(self) -> str:
        return "ollama"

    def _get_config(self, project_path: Path | None = None) -> tuple[str, str]:
        """
        Get endpoint and model from config or env vars.

        Returns:
            Tuple of (endpoint, model)
        """
        endpoint = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        model = os.environ.get("OLLAMA_MODEL", "llama3")

        if project_path:
            try:
                config = Config.load(project_path)
                # Check if env vars are NOT set, then use config.
                if "OLLAMA_HOST" not in os.environ:
                    endpoint = config.ollama.endpoint
                if "OLLAMA_MODEL" not in os.environ:
                    model = config.ollama.model
            except Exception as e:
                logger.warning(f"Failed to load project config: {e}")

        return endpoint, model

    def get_context_window_size(self, model: str | None = None) -> int:
        """
        Get context window size.
        Ollama models vary, but 8k or 128k are common.
        Default to 8k for safety unless known.
        """
        # TODO: Could query /api/show to get model details
        return 8192

    def supports_model_selection(self) -> bool:
        return True

    async def list_models(self) -> list[str]:
        """List available models from Ollama."""
        endpoint, _ = self._get_config()
        url = f"{endpoint}/api/tags"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=5.0)
                response.raise_for_status()
                data = response.json()
                # data["models"] is a list of dicts with "name" key
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def _check_availability(self) -> bool:
        """Check if Ollama server is reachable."""
        endpoint, _ = self._get_config()
        # Clean up endpoint if it has trailing slash
        endpoint = endpoint.rstrip("/")

        # Try root endpoint first (often returns "Ollama is running")
        # Or /api/version
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(endpoint, timeout=2.0)
                if response.status_code == 200:
                    return True
        except Exception as e:
            logger.debug(f"Ollama availability check failed at {endpoint}: {e}")
            return False

        return False

    def get_setup_instructions(self) -> str:
        return """
╔══════════════════════════════════════════════════════════════════════╗
║                    Ollama Server Not Reachable                       ║
╠══════════════════════════════════════════════════════════════════════╣
║ 1. Install Ollama: https://ollama.com/download                       ║
║                                                                      ║
║ 2. Start Ollama server:                                              ║
║    ollama serve                                                      ║
║                                                                      ║
║ 3. Pull a model (e.g., llama3):                                      ║
║    ollama pull llama3                                                ║
║                                                                      ║
║ 4. Verify configuration:                                             ║
║    Default endpoint: http://localhost:11434                          ║
║    Update .agent-pump/config.yml or set OLLAMA_HOST env var.         ║
╚══════════════════════════════════════════════════════════════════════╝
"""

    async def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
        extra_args: list[str] | None = None,
        auto_approve: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        Execute generation via Ollama API.
        """
        endpoint, default_model = self._get_config(project_path)
        endpoint = endpoint.rstrip("/")
        url = f"{endpoint}/api/generate"

        model = default_model

        # Handle extra_args for model override
        if extra_args:
            args_iter = iter(extra_args)
            for arg in args_iter:
                if arg == "--model":
                    try:
                        model = next(args_iter)
                    except StopIteration:
                        pass

        # Handle instance-level extra args
        if self._extra_args:
            args_iter = iter(self._extra_args)
            for arg in args_iter:
                if arg == "--model":
                    try:
                        model = next(args_iter)
                    except StopIteration:
                        pass

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {
                # "num_ctx": self.get_context_window_size(model) # Let server decide or config
            },
        }

        logger.info(f"Calling Ollama at {url} with model {model}")
        await self.log_command(project_path, "ollama_req.log", f"POST {url} model={model}", prompt)

        try:
            async with httpx.AsyncClient(timeout=float(timeout)) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        yield f"[ERROR] Ollama API returned status {response.status_code}\n"
                        error_text = await response.aread()
                        yield f"Details: {error_text.decode('utf-8', errors='replace')}\n"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        try:
                            chunk = json.loads(line)

                            if "response" in chunk:
                                yield chunk["response"]

                            if chunk.get("done", False):
                                duration = chunk.get("total_duration", 0) / 1e9
                                logger.info(f"Ollama generation done in {duration:.2f}s")

                        except json.JSONDecodeError:
                            logger.warning(f"Failed to decode JSON chunk: {line[:50]}...")

        except httpx.TimeoutException:
            yield f"\n[TIMEOUT] Request timed out after {timeout}s\n"
        except httpx.RequestError as e:
            yield f"\n[ERROR] Connection error: {e}\n"
            yield self.get_setup_instructions()
        except Exception as e:
            logger.exception("Unexpected error in Ollama backend")
            yield f"\n[ERROR] Unexpected error: {e}\n"
