"""Base prompt templates for different workflow phases."""

from pydantic import BaseModel, Field


class BasePromptTemplate(BaseModel):
    """Base template for workflow phase prompts."""

    name: str = Field(..., description="Name of the phase")
    description: str = Field(..., description="Description of the phase")
    icon: str = Field(..., description="Icon for the phase")
    template: str = Field(..., description="Prompt template")


BASE_PROMPTS = {
    "planning": BasePromptTemplate(
        name="planning",
        description="Creates ENGINEERING_PLAN.md from ROADMAP.md",
        icon="📋",
        template="""Create a detailed engineering plan to implement the requested feature.

Context:
- Current ROADMAP.md: {{ read_file("ROADMAP.md") }}
- Current ENGINEERING_PLAN.md: {{ read_file("ENGINEERING_PLAN.md") }}

Feature Request:
{{ read_file("TASK_NAME") }}

Requirements:
1. Format as ENGINEERING_PLAN.md with:
   - Feature description and goals
   - Detailed task list with checkboxes
   - Each task should be small and actionable
   - Include tasks for: implementation, testing, documentation
   - THE FINAL TASK MUST BE: (
      "Reflect on the work done and update BEST_PRACTICES.md with any "
      "lessons learned, and check if README.md needs updates as a result"
   )
2. Create a TASK_NAME file containing ONLY the exact title of the feature you are working on.


Be thorough but concise. The task list will guide the implementation phase.""",
    ),
    "implementing": BasePromptTemplate(
        name="implementing",
        description="Executes tasks from ENGINEERING_PLAN.md",
        icon="🔨",
        template="""Implement the tasks in ENGINEERING_PLAN.md.

Context:
- Current ROADMAP.md: {{ read_file("ROADMAP.md") }}
- Current ENGINEERING_PLAN.md: {{ read_file("ENGINEERING_PLAN.md") }}
- Current TASK_NAME: {{ read_file("TASK_NAME") }}

Requirements:
1. Follow the task list exactly
2. Update code, tests, documentation as needed
3. Maintain code quality and best practices
4. Keep changes focused on the current task
5. Update BEST_PRACTICES.md with any lessons learned during implementation
""",
    ),
    "verifying": BasePromptTemplate(
        name="verifying",
        description="Runs verification commands and fixes issues",
        icon="✅",
        template="""Verify the implementation by running verification commands and
fixing any issues.

Context:
- Current ROADMAP.md: {{ read_file("ROADMAP.md") }}
- Current ENGINEERING_PLAN.md: {{ read_file("ENGINEERING_PLAN.md") }}
- Current TASK_NAME: {{ read_file("TASK_NAME") }}

Requirements:
1. Run build, lint, and test commands as configured for this project
2. Fix any issues that arise
3. Ensure all verification commands pass
4. Update BEST_PRACTICES.md with any lessons learned during verification
""",
    ),
    "brainstorming": BasePromptTemplate(
        name="brainstorming",
        description="Updates ROADMAP.md with next features",
        icon="💡",
        template="""Brainstorm the next feature to work on based on current state.

Context:
- Current ROADMAP.md: {{ read_file("ROADMAP.md") }}
- Current ENGINEERING_PLAN.md: {{ read_file("ENGINEERING_PLAN.md") }}
- Current TASK_NAME: {{ read_file("TASK_NAME") }}

Requirements:
1. Review what was just implemented
2. Identify logical next steps or improvements
3. Add new features to ROADMAP.md in the "Future Enhancements" section
4. Prioritize features appropriately
5. Update BEST_PRACTICES.md with any lessons learned during brainstorming
""",
    ),
    "committing": BasePromptTemplate(
        name="committing",
        description="Commits changes with appropriate messages",
        icon="📦",
        template="""Commit the changes with appropriate git commit messages.

Context:
- Current ROADMAP.md: {{ read_file("ROADMAP.md") }}
- Current ENGINEERING_PLAN.md: {{ read_file("ENGINEERING_PLAN.md") }}
- Current TASK_NAME: {{ read_file("TASK_NAME") }}

Requirements:
1. Create a meaningful commit message based on the changes
2. Include reference to the feature being implemented
3. Follow conventional commit format
4. Update BEST_PRACTICES.md with any lessons learned during committing
""",
    ),
    "reviewing": BasePromptTemplate(
        name="reviewing",
        description="Auto-reviews code and suggests improvements",
        icon="🔍",
        template="""Review the current implementation and suggest improvements.

Context:
- Current ROADMAP.md: {{ read_file("ROADMAP.md") }}
- Current ENGINEERING_PLAN.md: {{ read_file("ENGINEERING_PLAN.md") }}
- Current TASK_NAME: {{ read_file("TASK_NAME") }}

Requirements:
1. Review the changes made for the current task
2. Analyze code quality, potential bugs, and edge cases
3. Suggest refactoring opportunities if applicable
4. Verify alignment with BEST_PRACTICES.md
5. Output your findings as a summary. The automated PR reviewer will run additional checks.

NOTE: This phase is for AI analysis. Automated linting and testing will run separately.
""",
    ),
}


class BasePromptManager:
    """Manager for accessing base prompt templates."""

    def get_default(self, phase: str) -> str:
        """Get the default base prompt template for a phase.

        Args:
            phase: The workflow phase name (e.g., "planning", "implementing")

        Returns:
            The template string for the phase, or empty string if not found.
        """
        if phase in BASE_PROMPTS:
            return BASE_PROMPTS[phase].template
        return ""

    def get_all_phases(self) -> list[str]:
        """Get all available phase names."""
        return list(BASE_PROMPTS.keys())


# Singleton instance
_manager_instance: BasePromptManager | None = None


def get_base_prompt_manager() -> BasePromptManager:
    """Get the singleton BasePromptManager instance."""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = BasePromptManager()
    return _manager_instance
