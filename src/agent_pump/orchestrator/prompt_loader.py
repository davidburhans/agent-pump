"""Prompt loader for directory-based configuration."""

from pathlib import Path
from typing import Literal


class PromptLoader:
    """Load prompts from .agent-pump/ directory structure."""

    def __init__(self, project_path: Path):
        self.prompt_dir = project_path / ".agent-pump"

    def has_directory_structure(self) -> bool:
        """Check if project uses directory-based config."""
        return (self.prompt_dir / "states").is_dir()

    def load_state_prompt(
        self, state: str, part: Literal["base", "pre", "post"] = "base"
    ) -> str | None:
        """Load prompt file. Returns None if not found."""
        filename = f"{state}.md" if part == "base" else f"{part}-{state}.md"
        path = self.prompt_dir / "states" / filename
        return path.read_text(encoding="utf-8").strip() if path.exists() else None

    def load_backend_prompt(self, backend: str, part: Literal["pre", "post"]) -> str | None:
        """Load backend-specific prompt."""
        path = self.prompt_dir / "backends" / f"{part}-{backend}.md"
        return path.read_text(encoding="utf-8").strip() if path.exists() else None

    def build_prompt(
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
        if pre := self.load_state_prompt(state, "pre"):
            parts.append(pre)
        if pre_backend := self.load_backend_prompt(backend, "pre"):
            parts.append(pre_backend)

        custom_base = self.load_state_prompt(state, "base")
        if custom_base:
            base = custom_base
            if context:
                base = base.format(**context)
        else:
            base = default_prompt

        parts.append(base)

        if post_backend := self.load_backend_prompt(backend, "post"):
            parts.append(post_backend)
        if post := self.load_state_prompt(state, "post"):
            parts.append(post)

        return "\n\n".join(parts)
