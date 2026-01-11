"""Base prompt templates and management for workflow phases.

This module provides configurable base prompts that can be viewed/edited in the TUI.
The BasePromptManager bridges between default prompts and custom overrides.
"""


from pydantic import BaseModel, Field


class BasePromptTemplate(BaseModel):
    """A configurable base prompt template."""

    name: str = Field(description="Phase name, e.g., 'planning', 'implementing'")
    description: str = Field(description="Human-readable description of this phase")
    default_content: str = Field(description="The default prompt content")
    icon: str = Field(default="", description="Emoji icon for this phase")
    editable: bool = Field(default=True, description="Whether users can override this prompt")


# Default base prompts for each phase
# These are the raw templates without branch instructions
BASE_PROMPT_TEMPLATES: dict[str, BasePromptTemplate] = {
    "planning": BasePromptTemplate(
        name="planning",
        description="Creates ENGINEERING_PLAN.md from ROADMAP.md",
        icon="📋",
        default_content="""You are starting the PLANNING phase for this project.

FIRST, check if ROADMAP.md and BEST_PRACTICES.md exist. If either is missing, create it:

**If ROADMAP.md is missing**, analyze the project and create one with:
- Status legend (🔴 Not Started, 🟡 In Progress, 🟢 Complete)
- "Current Sprint" section with 2-3 actionable features
- "Future Enhancements" section with ideas for later
- "Completed" section (empty initially)
- Each item should have: title, priority, description, acceptance criteria

**If BEST_PRACTICES.md is missing**, analyze the project and create one with:
- Project philosophy and goals
- Tech stack with rationale for each choice
- Code style guidelines (naming, formatting, patterns)
- Testing standards (what to test, coverage expectations)
- Error handling patterns
- Logging conventions
- Git practices (commit message format, branching)
- Verification checklist (commands to run before committing)
- "Lessons Learned" section (updated during development)

THEN, proceed with planning:
1. Read ROADMAP.md and identify the first uncompleted item (marked with 🔴 or "Not Started")
2. Read BEST_PRACTICES.md to understand the project's coding standards
3. Create a detailed ENGINEERING_PLAN.md with:
   - Feature description and goals
   - Detailed task list with checkboxes
   - Each task should be small and actionable
   - Include tasks for: implementation, testing, documentation
   - THE FINAL TASK MUST BE: "Reflect on the work done and update BEST_PRACTICES.md with any lessons learned, \
      and check if README.md needs updates as a result"
6. Create a TASK_NAME file containing ONLY the exact title of the feature you are working on.


Be thorough but concise. The task list will guide the implementation phase.""",
    ),
    "implementing": BasePromptTemplate(
        name="implementing",
        description="Executes tasks from ENGINEERING_PLAN.md",
        icon="🔨",
        default_content="""You are in the IMPLEMENTING phase.

Your task:
1. Read ENGINEERING_PLAN.md to understand the tasks
2. Execute each task in the checklist, marking them complete as you go
3. For each code change:
   - Follow BEST_PRACTICES.md guidelines
   - Ensure the code builds without errors
   - Ensure linting passes
   - Ensure tests pass (run the test command)
4. Complete ALL tasks including the final reflection task to update BEST_PRACTICES.md 
   and check README.md

Work through the entire task list systematically. Do not skip any tasks.""",
    ),
    "verifying": BasePromptTemplate(
        name="verifying",
        description="Runs verification checklist from BEST_PRACTICES.md",
        icon="✅",
        default_content="""You are in the VERIFYING phase.

Your task is to ensure the codebase is healthy and meets standards before proceeding.

1. Read BEST_PRACTICES.md to find the "Verification Checklist" section.
2. Run each verification command listed (e.g., tests, linting, type checking).
3. If ANY command fails:
   - Analyze the error output.
   - Fix the issue in the code.
   - Re-run the verification command to confirm the fix.
   - Repeat until ALL checks pass.
4. Ensure no new files were created that violate .gitignore or project standards.

Do NOT proceed to the next phase until all verification steps pass successfully.""",
    ),
    "brainstorming": BasePromptTemplate(
        name="brainstorming",
        description="Updates ROADMAP.md with new ideas",
        icon="💡",
        default_content="""You are in the BRAINSTORMING phase.

Your task:
1. Review the feature you just implemented
2. Update ROADMAP.md:
   - Mark the completed feature as 🟢 Complete
   - Move it to the "Completed" section
3. Brainstorm and add NEW feature ideas to "Future Enhancements"
4. For EACH new idea you add, also promote ONE existing "Future Enhancement":
   - Select an existing future item that would be valuable
   - Flesh it out with detailed acceptance criteria
   - Move it from "Future Enhancements" to "Current Sprint" (mark as 🔴 Not Started)
   This ensures the roadmap always has ready-to-implement items.
5. Delete ENGINEERING_PLAN.md (it's no longer needed)
6. Delete TASK_NAME (it's no longer needed)


Focus on practical, valuable improvements that align with the project's goals.""",
    ),
    "committing": BasePromptTemplate(
        name="committing",
        description="Commits changes to git",
        icon="📝",
        default_content="""You are in the COMMITTING phase.

Your task:
1. Use `git status` to see what files have changed
2. Add ONLY the files you modified using `git add <specific-file>` for each file
   - NEVER use `git add .` or `git add -A`
   - Do NOT add any files in the .gemini/ directory
   - Do NOT add any files in __pycache__/ or .pytest_cache/
3. Write a clear, conventional commit message describing the feature
   - Format: type(scope): description
   - Example: feat(auth): add user login functionality
4. Commit the changes with `git commit`
5. Push to the remote repository

Verify each step succeeded before moving to the next.""",
    ),
}


class BasePromptManager:
    """Manages base prompt templates with override support.
    
    This class provides a clean interface for retrieving prompts, supporting
    both default templates and custom overrides (stored per-project).
    """

    def __init__(self) -> None:
        """Initialize the manager with default templates."""
        self._templates = BASE_PROMPT_TEMPLATES.copy()

    def get_default(self, phase: str) -> str:
        """Get the default prompt content for a phase.
        
        Args:
            phase: Phase name (planning, implementing, verifying, brainstorming, committing)
            
        Returns:
            The default prompt content.
            
        Raises:
            KeyError: If phase is not found.
        """
        template = self._templates.get(phase)
        if template is None:
            raise KeyError(f"Unknown phase: {phase}")
        return template.default_content

    def get_prompt(self, phase: str, custom_override: str | None = None) -> str:
        """Get the prompt for a phase, with optional override.
        
        Args:
            phase: Phase name
            custom_override: If provided and non-empty, use this instead of default
            
        Returns:
            The prompt content (custom override if provided, else default).
        """
        if custom_override and custom_override.strip():
            return custom_override.strip()
        return self.get_default(phase)

    def get_template(self, phase: str) -> BasePromptTemplate | None:
        """Get the full template for a phase.
        
        Args:
            phase: Phase name
            
        Returns:
            The template, or None if not found.
        """
        return self._templates.get(phase)

    def list_phases(self) -> list[str]:
        """List all available phase names.
        
        Returns:
            List of phase names in workflow order.
        """
        # Return in workflow order
        return ["planning", "implementing", "verifying", "brainstorming", "committing"]

    def get_all_templates(self) -> dict[str, BasePromptTemplate]:
        """Get all templates.
        
        Returns:
            Dictionary of phase name to template.
        """
        return self._templates.copy()


# Module-level singleton for convenience
_manager: BasePromptManager | None = None


def get_base_prompt_manager() -> BasePromptManager:
    """Get the singleton BasePromptManager instance.
    
    Returns:
        The shared BasePromptManager.
    """
    global _manager
    if _manager is None:
        _manager = BasePromptManager()
    return _manager


def get_base_prompt(phase: str) -> str:
    """Convenience function to get the default prompt for a phase.
    
    Args:
        phase: Phase name
        
    Returns:
        The default prompt content.
    """
    return get_base_prompt_manager().get_default(phase)
