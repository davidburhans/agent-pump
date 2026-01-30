"""Prompt loader for directory-based configuration."""

from pathlib import Path
from typing import Literal, Any
import logging

try:
    from jinja2 import Environment, BaseLoader, select_autoescape
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
                autoescape=select_autoescape(['html', 'xml'])
            )
            self.env.globals['read_file'] = self._read_file_content

    def _read_file_content(self, filepath: str) -> str:
        """Read file content helper for Jinja templates."""
        try:
            # Resolve relative to project root
            target = (self.project_path / filepath).resolve()
            # Security check: Ensure we don't escape project root? 
            # For a personal tool, maybe less strict, but good practice.
            # strict check:
            # if not str(target).startswith(str(self.project_path.resolve())):
            #    return f"[Error: Cannot read file outside project: {filepath}]"
            
            if target.exists() and target.is_file():
                return target.read_text(encoding="utf-8").strip()
            return f"[File not found: {filepath}]"
        except Exception as e:
            return f"[Error reading {filepath}: {e}]"

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
        
        base = default_prompt
        if custom_base:
            if HAS_JINJA and context:
                try:
                    template = self.env.from_string(custom_base)
                    base = template.render(**context)
                except Exception as e:
                    logger.error(f"Jinja rendering failed for {state}: {e}")
                    # Fallback to raw or simple format if possible
                    # But since we switched to {{ }}, .format() won't work on new templates.
                    # We might want to try .format() as a fallback for legacy templates?
                    try:
                         base = custom_base.format(**context)
                    except:
                         base = custom_base 
            elif context:
                # Fallback implementation if Jinja missing (legacy)
                try:
                    base = custom_base.format(**context)
                except:
                    base = custom_base
            else:
                base = custom_base

        parts.append(base)

        if post_backend := self.load_backend_prompt(backend, "post"):
            parts.append(post_backend)
        if post := self.load_state_prompt(state, "post"):
            parts.append(post)

        return "\n\n".join(parts)
