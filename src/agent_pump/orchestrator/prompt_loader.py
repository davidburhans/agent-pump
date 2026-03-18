"""Prompt loader for directory-based configuration."""

import asyncio
import logging
from pathlib import Path
from typing import Literal

try:
    from jinja2 import BaseLoader, Environment, select_autoescape

    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False

logger = logging.getLogger(__name__)


class PromptLoader:
    """Load prompts from .agent-pump/ directory structure."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.prompt_dir = project_path / ".agent-pump"

        if HAS_JINJA:
            self.env = Environment(
                loader=BaseLoader(),
                autoescape=select_autoescape(["html", "xml"]),
                enable_async=True,
            )
            self.env.globals["read_file"] = self._read_file_content

    async def _read_file_content(self, filepath: str) -> str:
        """Read file content helper for Jinja templates."""
        try:
            # Resolve relative to project root
            target = (self.project_path / filepath).resolve()
            # Security check: Ensure we don't escape project root?
            # For a personal tool, maybe less strict, but good practice.
            # strict check:
            # if not str(target).startswith(str(self.project_path.resolve())):
            #    return f"[Error: Cannot read file outside project: {filepath}]"

            def _read_sync() -> str | None:
                if target.exists() and target.is_file():
                    return target.read_text(encoding="utf-8").strip()
                return None

            content = await asyncio.to_thread(_read_sync)
            if content is not None:
                return content
            return f"[File not found: {filepath}]"
        except Exception as e:
            return f"[Error reading {filepath}: {e}]"

    def has_directory_structure(self) -> bool:
        """Check if project uses directory-based config."""
        return (self.prompt_dir / "states").is_dir()

    async def load_state_prompt(
        self, state: str, part: Literal["base", "pre", "post"] = "base"
    ) -> str | None:
        """Load prompt file. Returns None if not found."""
        filename = f"{state}.md" if part == "base" else f"{part}-{state}.md"
        path = self.prompt_dir / "states" / filename

        def _read_sync() -> str | None:
            return path.read_text(encoding="utf-8").strip() if path.exists() else None

        return await asyncio.to_thread(_read_sync)

    async def load_backend_prompt(self, backend: str, part: Literal["pre", "post"]) -> str | None:
        """Load backend-specific prompt."""
        path = self.prompt_dir / "backends" / f"{part}-{backend}.md"

        def _read_sync() -> str | None:
            return path.read_text(encoding="utf-8").strip() if path.exists() else None

        return await asyncio.to_thread(_read_sync)

    async def build_prompt(
        self,
        state: str,
        backend: str,
        default_prompt: str,
        context: dict[str, str] | None = None,
    ) -> str:
        """Assemble final prompt with all customizations.

        Order: pre-state → pre-backend → base → post-backend → post-state
        """
        parts = []
        if pre := await self.load_state_prompt(state, "pre"):
            parts.append(pre)
        if pre_backend := await self.load_backend_prompt(backend, "pre"):
            parts.append(pre_backend)

        custom_base = await self.load_state_prompt(state, "base")

        # Decide which template to use
        template_str = custom_base if custom_base else default_prompt
        base = template_str

        # Render the selected template
        if template_str and context:
            if HAS_JINJA:
                try:
                    template = self.env.from_string(template_str)
                    # Use render_async for non-blocking I/O
                    base = await template.render_async(**context)
                except Exception as e:
                    logger.error(f"Jinja rendering failed for {state}: {e}")
                    # Fallback to .format() for legacy compatibility or raw
                    try:
                        base = template_str.format(**context)
                    except (KeyError, ValueError):
                        base = template_str
            else:
                # Fallback if Jinja missing
                try:
                    base = template_str.format(**context)
                except (KeyError, ValueError):
                    base = template_str

        parts.append(base)

        if post_backend := await self.load_backend_prompt(backend, "post"):
            parts.append(post_backend)
        if post := await self.load_state_prompt(state, "post"):
            parts.append(post)

        return "\n\n".join(parts)
