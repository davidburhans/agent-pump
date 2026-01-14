"""Prompt builders for different workflow phases."""

from collections.abc import Sequence


def build_planning_prompt(
    feature_request: str,
    roadmap_content: str,
    engineering_plan_content: str,
    task_name_content: str,
    branch: str | None = None,
) -> str:
    """Build the prompt for the planning phase."""
    branch_instruction = f"\n\nIMPORTANT: Work on branch '{branch}'.\n" if branch else ""
    return f"""{branch_instruction}Create a detailed engineering plan to implement the requested \
feature.

Context:
- Current ROADMAP.md: {roadmap_content}
- Current ENGINEERING_PLAN.md: {engineering_plan_content}

Feature Request:
{feature_request}

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
6. Create a TASK_NAME file containing ONLY the exact title of the feature you are working on.


Be thorough but concise. The task list will guide the implementation phase."""


def build_implementing_prompt(branch: str | None = None) -> str:
    """Build the prompt for the implementing phase."""
    branch_instruction = f"\n\nIMPORTANT: Work on branch '{branch}'.\n" if branch else ""

    return f"""{branch_instruction}Execute the tasks in ENGINEERING_PLAN.md.

Context:
- Current ROADMAP.md: {{roadmap_content}}
- Current ENGINEERING_PLAN.md: {{engineering_plan_content}}
- Current TASK_NAME: {{task_name_content}}

Requirements:
1. Follow the task list exactly
2. Update code, tests, documentation as needed
3. Maintain code quality and best practices
4. Keep changes focused on the current task
5. Update BEST_PRACTICES.md with any lessons learned during implementation"""


def build_verifying_prompt(branch: str | None = None) -> str:
    """Build the prompt for the verifying phase."""
    branch_instruction = f"\n\nIMPORTANT: Work on branch '{branch}'.\n" if branch else ""

    return f"""{branch_instruction}Verify the implementation by running verification commands and
fixing any issues.

Context:
- Current ROADMAP.md: {{roadmap_content}}
- Current ENGINEERING_PLAN.md: {{engineering_plan_content}}
- Current TASK_NAME: {{task_name_content}}

Requirements:
1. Run build, lint, and test commands as configured for this project
2. Fix any issues that arise
3. Ensure all verification commands pass
4. Update BEST_PRACTICES.md with any lessons learned during verification"""


def build_brainstorming_prompt(
    roadmap_content: str,
    engineering_plan_content: str,
    task_name_content: str,
    queued_ideas: Sequence[str] | None = None,
) -> str:
    """Build the prompt for the brainstorming phase.

    Args:
        queued_ideas: Optional list of user-submitted ideas to consider
    """
    ideas_section = ""
    if queued_ideas:
        ideas_section = "\n\n## USER-SUBMITTED IDEAS TO CONSIDER\n"
        ideas_section += (
            "The user has submitted the following ideas. Please evaluate each one "
            "and add any valuable ideas to the roadmap:\n\n"
        )
        for i, idea in enumerate(queued_ideas, 1):
            ideas_section += f"{i}. {idea}\n"
        ideas_section += "\nFor each submitted idea:\n"
        ideas_section += "- If valuable: Add to 'Future Enhancements' with acceptance criteria\n"
        ideas_section += (
            "- If not suitable: You may skip it (the user understands not all ideas make it)\n"
        )

    return f"""Brainstorm the next feature to work on based on current state.

Context:
- Current ROADMAP.md: {roadmap_content}
- Current ENGINEERING_PLAN.md: {engineering_plan_content}
- Current TASK_NAME: {task_name_content}
{ideas_section}

Your task:
1. Review the feature you just implemented
2. Update ROADMAP.md:
   - Remove the completed feature from the list (do not just mark it as complete, remove it
     entirely to keep the roadmap focused)
   - Ensure the "current Sprint" pointers match the new top priority
3. Documentation:
   - Check if FEATURES.md exists. If not, create it.
   - FEATURES.md should contain a list of features with:
     - Feature Name
     - Description (what it does)
     - Status (planned, in-progress, completed)
     - Link to relevant documentation
4. Update BEST_PRACTICES.md with any lessons learned during brainstorming"""


def build_committing_prompt(branch: str | None = None) -> str:
    """Build the prompt for the committing phase."""
    branch_instruction = f"\n\nIMPORTANT: Work on branch '{branch}'.\n" if branch else ""

    return f"""{branch_instruction}Commit the changes with appropriate git commit messages.

Context:
- Current ROADMAP.md: {{roadmap_content}}
- Current ENGINEERING_PLAN.md: {{engineering_plan_content}}
- Current TASK_NAME: {{task_name_content}}

Requirements:
1. Create a meaningful commit message based on the changes
2. Include reference to the feature being implemented
3. Follow conventional commit format
4. Update BEST_PRACTICES.md with any lessons learned during committing"""
