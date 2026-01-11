"""Prompt templates for workflow phases."""


def get_branch_instructions(branch: str | None) -> str:
    """Get prompt instructions for branch handling."""
    if not branch:
        return ""
    return f"""
IMPORTANT: All work must be done on branch '{branch}'.
Before starting, run: git checkout {branch} || git checkout -b {branch}
Ensure you are on this branch before making any changes.
"""


def build_planning_prompt(branch: str | None = None) -> str:
    """Build the prompt for the planning phase."""
    branch_instructions = get_branch_instructions(branch)
    return f"""{branch_instructions}
You are starting the PLANNING phase for this project.

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

Be thorough but concise. The task list will guide the implementation phase.
"""


def build_implementing_prompt(branch: str | None = None) -> str:
    """Build the prompt for the implementing phase."""
    branch_instructions = get_branch_instructions(branch)
    return f"""{branch_instructions}
You are in the IMPLEMENTING phase.

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

Work through the entire task list systematically. Do not skip any tasks.
"""


def build_verifying_prompt(branch: str | None = None) -> str:
    """Build the prompt for the verifying phase."""
    branch_instructions = get_branch_instructions(branch)
    return f"""{branch_instructions}
You are in the VERIFYING phase.

Your task is to ensure the codebase is healthy and meets standards before proceeding.

1. Read BEST_PRACTICES.md to find the "Verification Checklist" section.
2. Run each verification command listed (e.g., tests, linting, type checking).
3. If ANY command fails:
   - Analyze the error output.
   - Fix the issue in the code.
   - Re-run the verification command to confirm the fix.
   - Repeat until ALL checks pass.
4. Ensure no new files were created that violate .gitignore or project standards.

Do NOT proceed to the next phase until all verification steps pass successfully.
"""


def build_brainstorming_prompt() -> str:
    """Build the prompt for the brainstorming phase."""
    return """
You are in the BRAINSTORMING phase.

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

Focus on practical, valuable improvements that align with the project's goals.
"""


def build_committing_prompt(branch: str | None = None) -> str:
    """Build the prompt for the committing phase."""
    branch_instructions = get_branch_instructions(branch)
    return f"""{branch_instructions}
You are in the COMMITTING phase.

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

Verify each step succeeded before moving to the next.
"""
