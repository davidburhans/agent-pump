"""Workflow state machine using pytransitions."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from transitions import Machine

from agent_pump.backends import create_fallback_runner_from_config, get_backend
from agent_pump.backends.base import AgentBackend
from agent_pump.backends.gemini import GeminiBackend
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.models.state import WorkflowState
from agent_pump.models.workspace import PhaseBackends, ProjectConfig, PromptCustomization
from agent_pump.orchestrator.prompts import (
    build_brainstorming_prompt,
    build_committing_prompt,
    build_implementing_prompt,
    build_planning_prompt,
    build_verifying_prompt,
)
from agent_pump.orchestrator.verification_executor import VerificationExecutor

logger = logging.getLogger(__name__)


class BackendRunner(Protocol):
    """Protocol for something that can run agent prompts."""

    def run(
        self,
        project_path: Path,
        prompt: str,
        timeout: int = 600,
        verbose: bool = False,
        extra_args: list[str] | None = None,
    ) -> AsyncIterator[str]: ...


class ProjectWorkflow:
    """
    State machine for managing a project's development workflow.

    Uses pytransitions for state management with visualization support.
    """

    # Define states matching ProjectStatus
    states = [
        "idle",
        "planning",
        "implementing",
        "verifying",
        "brainstorming",
        "committing",
        "error",
        "completed",
    ]

    # Define transitions
    transitions = [
        {"trigger": "start", "source": "idle", "dest": "planning"},
        {"trigger": "plan_complete", "source": "planning", "dest": "implementing"},
        {"trigger": "plan_failed", "source": "planning", "dest": "error"},
        {"trigger": "implement_complete", "source": "implementing", "dest": "verifying"},
        {"trigger": "implement_failed", "source": "implementing", "dest": "error"},
        {"trigger": "verify_complete", "source": "verifying", "dest": "brainstorming"},
        {"trigger": "verify_failed", "source": "verifying", "dest": "error"},
        {"trigger": "brainstorm_complete", "source": "brainstorming", "dest": "committing"},
        {"trigger": "commit_complete", "source": "committing", "dest": "planning"},
        {"trigger": "no_more_features", "source": "committing", "dest": "completed"},
        {"trigger": "reset", "source": "error", "dest": "idle"},
        {"trigger": "restart", "source": "completed", "dest": "planning"},
    ]

    def __init__(
        self,
        project: Project,
        backend: AgentBackend | None = None,
        config: Any | None = None,  # Legacy file-based config
        project_config: ProjectConfig | None = None,  # New workspace config
        phase_backends: PhaseBackends | None = None,
        prompt_customization: PromptCustomization | None = None,
        idea_queue: list[str] | None = None,
        on_output: Callable[[str, str, str | None], None] | None = None,
        on_state_change: Callable[[str, str], None] | None = None,
        on_ideas_processed: Callable[[Path], None] | None = None,
    ):
        """
        Initialize the workflow for a project.

        Args:
            project: The project to manage
            backend: The AI agent backend to use (defaults to GeminiBackend)
            config: The legacy application configuration
            project_config: The project configuration (includes timeout, phase_backends, etc.)
            phase_backends: Optional phase-specific backend configuration
                            (overrides project_config if passed)
            prompt_customization: Optional per-phase prompt prefix/suffix overrides
            idea_queue: Optional list of ideas to include in brainstorming
            on_output: Callback for agent output lines
            on_state_change: Callback for state changes (old_state, new_state)
            on_ideas_processed: Callback when ideas have been processed
        """
        self.project = project
        self.backend = backend or GeminiBackend()
        self.config = config
        self.project_config = project_config
        self.phase_backends = phase_backends or (
            project_config.phase_backends if project_config else None
        )
        self.prompt_customization = prompt_customization or (
            project_config.prompt_customization if project_config else PromptCustomization()
        )
        self.idea_queue = idea_queue or []
        self.on_output = on_output
        self.on_state_change = on_state_change
        self.on_ideas_processed = on_ideas_processed
        self._running = False
        self._cancelled = False

        # Initialize verification executor with project's verification config
        self.verification_executor = VerificationExecutor(
            project_path=project.path, config=project.config
        )

        # Load or create workflow state
        self.workflow_state = WorkflowState.load(project.path) or WorkflowState(
            project_path=project.path
        )

        # Initialize state machine
        self.machine = Machine(
            model=self,
            states=self.states,
            transitions=self.transitions,
            initial=self.workflow_state.current_state,
            auto_transitions=False,
            after_state_change=self._after_state_change,
        )

        # Sync initial state from TASK_NAME or persisted state
        self._check_task_name_file()
        if not self.project.current_feature and self.workflow_state.current_feature:
            self.project.current_feature = self.workflow_state.current_feature

        # Sync project status from loaded state
        try:
            self.project.status = ProjectStatus(self.workflow_state.current_state)
        except ValueError:
            logger.warning(f"Invalid state in workflow state: {self.workflow_state.current_state}")
            self.project.status = ProjectStatus.IDLE

        # Sync feature history
        self.project.completed_features = self.workflow_state.completed_features.copy()
        self.project.failed_features = self.workflow_state.failed_features.copy()

        # Workspace reference (optional)
        self.workspace = None

    def _read_file_content(self, filename: str) -> str:
        """Read content of a file from the project directory."""
        try:
            file_path = self.project.path / filename
            if file_path.exists():
                return file_path.read_text(encoding="utf-8").strip()
        except Exception as e:
            logger.warning(f"Error reading {filename}: {e}")
        return "(File not found or empty)"

    def _get_context_content(self) -> dict[str, str]:
        """Get the context content for prompts."""
        return {
            "roadmap_content": self._read_file_content("ROADMAP.md"),
            "engineering_plan_content": self._read_file_content("ENGINEERING_PLAN.md"),
            "task_name_content": self._read_file_content("TASK_NAME"),
        }

    def _after_state_change(self, *args: Any, **kwargs: Any) -> None:
        """Called after each state change."""
        old_state = self.workflow_state.current_state
        new_state = self.state  # type: ignore

        # Clear granular activity on state change
        self.project.current_activity = None

        # Update workflow state
        self.workflow_state.current_state = new_state
        self.workflow_state.current_feature = self.project.current_feature
        self.workflow_state.completed_features = self.project.completed_features
        self.workflow_state.failed_features = self.project.failed_features
        self.workflow_state.last_updated = datetime.now()

        # Update project status
        try:
            self.project.status = ProjectStatus(new_state)
            self.project.state_changed_at = datetime.now()
        except ValueError:
            pass

        # Save state
        self.workflow_state.save()

        # Notify callback
        if self.on_state_change:
            self.on_state_change(old_state, new_state)

        logger.info(f"State changed: {old_state} -> {new_state}")

    def _check_task_name_file(self) -> None:
        """Check TASK_NAME file and update project state."""
        try:
            task_file = self.project.path / "TASK_NAME"
            if task_file.exists():
                content = task_file.read_text(encoding="utf-8").strip()
                if content:
                    self.project.current_feature = content
            elif self.state == "brainstorming" or self.state == "completed":
                # If file is gone and we are in a phase where it should be gone, clear it
                self.project.current_feature = None
        except Exception as e:
            logger.warning(f"Error reading TASK_NAME: {e}")

    def _parse_activity(self, line: str) -> None:
        """Parse output line for activity indicators and update state."""
        line_clean = line.strip()
        activity = None

        # Common patterns for tool usage
        if "Running tool:" in line:
            activity = line.split("Running tool:", 1)[1].strip()
        elif "Calling tool:" in line:
            activity = line.split("Calling tool:", 1)[1].strip()
        elif "Executing command:" in line:
            activity = line.split("Executing command:", 1)[1].strip()
        # FallbackBackendRunner specific log
        elif "[BACKEND] Using" in line:
            activity = "Switching backend..."

        # If activity detected and different from current, update and notify
        if activity and activity != self.project.current_activity:
            self.project.current_activity = activity
            # Trigger UI refresh by notifying state change (even if state is same)
            if self.on_state_change:
                self.on_state_change(self.workflow_state.current_state, self.workflow_state.current_state)

    def _emit_output(self, line: str) -> None:
        """Emit output line to callback."""
        self._parse_activity(line)
        if self.on_output:
            # Pass current state and current feature as metadata
            self.on_output(line, self.workflow_state.current_state, self.project.current_feature)

    def _get_backend_for_phase(self, phase: str) -> BackendRunner:
        """
        Get the backend(s) to use for a specific phase.

        Args:
            phase: Phase name (planning, implementing, verifying, brainstorming, committing)

        Returns:
            AgentBackend or FallbackBackendRunner for the phase
        """
        # Try to get phase-specific config
        phase_config = None
        if self.phase_backends:
            phase_config = getattr(self.phase_backends, phase, None)

        # Determine which backend list to use
        backends_to_use = []

        # 1. Use phase-specific backends if they exist and are not empty
        if phase_config and phase_config.backends:
            # Check if it's just a "use default" placeholder or actual config
            # (Assuming empty backends list means "use default", but it initiates with 1 default)
            # Actually, standard init is [BackendInstance()].
            # We need a way to know if user EXPLICITLY wants project default.
            # For now, let's assume if the phase backends are valid, we use them.
            # But the user request says "can be overridden at the per step level".
            # This implies the project default is the BASE, and steps override it.
            # So if step config exists, it wins.
            backends_to_use = phase_config.backends

        # 2. Fallback to project-level default chain
        # Try to get project config if not already available
        project_config = self.project_config
        if not project_config and self.workspace:
            project_config = self.workspace.get_project_config(self.project.path)

        if not backends_to_use and project_config and project_config.default_chain:
            backends_to_use = project_config.default_chain.backends

        # 3. Fallback to app-level/hardcoded default (Gemini)
        if not backends_to_use:
            return self.backend

        # Single backend logic
        if len(backends_to_use) == 1:
            instance = backends_to_use[0]
            try:
                backend = get_backend(instance.name)
                if instance.args:
                    backend._extra_args = instance.args  # type: ignore
                return backend
            except ValueError:
                logger.warning(f"Unknown backend '{instance.name}', using default")
                return self.backend

        # Multiple backends logic
        try:
            return create_fallback_runner_from_config(backends_to_use)
        except ValueError as e:
            logger.warning(f"Failed to create fallback runner: {e}, using default")
            return self.backend

    def _extract_model_from_args(self, args: list[str] | None) -> str | None:
        """Extract model name from command line arguments."""
        if not args:
            return None
        try:
            # Look for --model <name>
            if "--model" in args:
                idx = args.index("--model")
                if idx + 1 < len(args):
                    return args[idx + 1]
        except ValueError:
            pass
        return None

    async def run_phase(self, prompt: str, phase_name: str) -> bool:
        """
        Run a single phase by invoking the agent.

        Args:
            prompt: The prompt to send to the agent
            phase_name: Name of the phase for logging

        Returns:
            True if successful, False otherwise
        """
        self.workflow_state.log_phase_start(phase_name)
        self._emit_output(f"\n{'=' * 60}\n")
        self._emit_output(f"Starting {phase_name} phase...\n")
        self._emit_output(f"{'=' * 60}\n\n")

        start_time = datetime.now()
        output_lines: list[str] = []
        success = True

        # Get the backend for this phase
        backend = self._get_backend_for_phase(phase_name)

        # Initialize metrics
        metrics_backend_name = str(backend.name)  # Use str() in case it's a proxy
        metrics_model_name = None

        # If it's a single backend (not fallback runner), try to get model from attached args
        if hasattr(backend, "_extra_args"):
            metrics_model_name = self._extract_model_from_args(getattr(backend, "_extra_args"))

        # If it's a fallback runner, we'll rely on parsing the logs,
        # but defaulting to "Fallback Runner" as backend name is fine initially.
        if "FallbackBackendRunner" in str(type(backend)):
            metrics_backend_name = "Fallback Runner (Pending)"

        # Determine timeout:
        # 1. Start with project configuration default (default 1800s / 30m)
        timeout = 1800
        if self.project_config:
            timeout = self.project_config.default_timeout

        # Checking old config.workflow location just in case legacy
        if (
            self.config
            and hasattr(self.config, "workflow")
            and hasattr(self.config.workflow, "timeout")
        ):
            timeout = self.config.workflow.timeout

        # 2. Check for step-specific override in PhaseBackends
        if self.phase_backends:
            phase_config = getattr(self.phase_backends, phase_name, None)
            if phase_config and phase_config.backends:
                # Use the timeout from the first backend in the chain if set
                # (For fallback chains, we strictly use the first one's timeout preference for now
                # to keep it simple, or we could pass it down to the fallback runner)
                step_timeout = phase_config.backends[0].timeout
                if step_timeout is not None and step_timeout > 0:
                    timeout = step_timeout

        try:
            async for line in backend.run(
                project_path=self.project.path,
                prompt=prompt,
                timeout=timeout,
            ):
                if self._cancelled:
                    self._emit_output("\n[PAUSED] Workflow paused by user\n")
                    # Don't mark as failed, but loop will be broken
                    success = False
                    break

                # Check for explicit error markers
                if "[ERROR]" in line or "[TIMEOUT]" in line:
                    success = False

                output_lines.append(line)
                self._emit_output(line)

                # Parse [BACKEND] line from FallbackBackendRunner
                # Format: [BACKEND] Using Gemini CLI (args: ['--model', 'gemini-1.5-pro'])
                if line.startswith("[BACKEND] Using"):
                    try:
                        # naive parse
                        parts = line.split("Using ", 1)
                        if len(parts) > 1:
                            details = parts[1].strip()
                            if "(args:" in details:
                                name_part, args_part = details.split("(args:", 1)
                                metrics_backend_name = name_part.strip()
                                # Clean up args string to list-like
                                args_clean = args_part.rstrip(")").strip()
                                # It's a string representation of a list, e.g. "['--model', 'foo']"
                                # We can't safely eval it, but we can regex or simple check
                                if "'--model'" in args_clean or '"--model"' in args_clean:
                                    # Simple extraction for now
                                    import re

                                    match = re.search(
                                        r"['\"]--model['\"],\s*['\"]([^'\"]+)['\"]", args_clean
                                    )
                                    if match:
                                        metrics_model_name = match.group(1)
                            else:
                                metrics_backend_name = details
                    except Exception as e:
                        logger.warning(f"Failed to parse backend info log: {e}")

        except Exception as e:
            logger.exception(f"Error in {phase_name} phase")
            self._emit_output(f"\n[ERROR] {e}\n")
            success = False

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # specific check for min execution time
        if success and not self._cancelled:
            if duration < self.project.min_execution_time_seconds:
                self._emit_output(
                    f"\n[ERROR] Backend execution too short ({duration:.1f}s < {self.project.min_execution_time_seconds}s). Assuming failure.\n"  # noqa: E501
                )
                success = False

        # Fail if no output received and not cancelled
        if not output_lines and success and not self._cancelled:
            self._emit_output("\n[ERROR] No output received from backend\n")
            success = False

        # Log phase completion
        summary = "".join(output_lines[-10:]) if output_lines else None
        self.workflow_state.log_phase_complete(
            success=success,
            summary=summary,
            backend=metrics_backend_name,
            model=metrics_model_name,
            duration_seconds=duration,
        )
        self.workflow_state.save()

        return success

    async def run(self, max_iterations: int = 10) -> None:
        """
        Run the full workflow loop.

        Args:
            max_iterations: Maximum number of plan->implement->commit cycles
        """
        if self._running:
            raise RuntimeError("Workflow is already running")

        self._running = True
        self._cancelled = False

        try:
            # Start if idle
            if self.state == "idle":  # type: ignore
                self.start()  # type: ignore

            iteration = 0
            while iteration < max_iterations and not self._cancelled:
                current_state = self.state  # type: ignore

                if current_state == "idle":
                    self.start()  # type: ignore
                    continue

                if current_state == "planning":
                    context = self._get_context_content()
                    base_prompt = build_planning_prompt(
                        feature_request=context["task_name_content"],
                        roadmap_content=context["roadmap_content"],
                        engineering_plan_content=context["engineering_plan_content"],
                        task_name_content=context["task_name_content"],
                        branch=self.project.branch,
                    )
                    prompt = self.prompt_customization.apply_to_prompt("planning", base_prompt)
                    success = await self.run_phase(prompt, "planning")
                    if self._cancelled:
                        break
                    if success:
                        self._check_task_name_file()
                        self.plan_complete()  # type: ignore
                    else:
                        self.plan_failed()  # type: ignore

                elif current_state == "implementing":
                    context = self._get_context_content()
                    base_prompt_template = build_implementing_prompt(self.project.branch)
                    base_prompt = base_prompt_template.format(**context)
                    prompt = self.prompt_customization.apply_to_prompt("implementing", base_prompt)
                    success = await self.run_phase(prompt, "implementing")
                    if self._cancelled:
                        break
                    if success:
                        self.implement_complete()  # type: ignore
                    else:
                        self.implement_failed()  # type: ignore

                elif current_state == "verifying":
                    context = self._get_context_content()
                    # First run the AI verification phase
                    base_prompt_template = build_verifying_prompt(self.project.branch)
                    base_prompt = base_prompt_template.format(**context)
                    prompt = self.prompt_customization.apply_to_prompt("verifying", base_prompt)
                    ai_success = await self.run_phase(prompt, "verifying")

                    if self._cancelled:
                        break

                    # Then run the custom verification commands
                    if ai_success:
                        self._emit_output("\n[INFO] Running custom verification commands...\n")

                        # Run all verification commands
                        verification_results = await self.verification_executor.run_all()

                        # Check if all verification commands passed
                        all_passed = all(result.success for result in verification_results.values())

                        # Log verification results
                        for cmd_type, result in verification_results.items():
                            status = "PASSED" if result.success else "FAILED"
                            self._emit_output(
                                f"\n[{status}] {cmd_type.upper()} command: {result.command or 'N/A'}"  # noqa: E501
                            )
                            if result.stdout:
                                self._emit_output(f"STDOUT:\n{result.stdout}")
                            if result.stderr:
                                self._emit_output(f"STDERR:\n{result.stderr}")
                            self._emit_output(f"DURATION: {result.duration:.2f}s\n")

                        if all_passed:
                            self._emit_output("\n[SUCCESS] All verification commands passed!\n")
                            self.verify_complete()  # type: ignore
                        else:
                            self._emit_output("\n[ERROR] Some verification commands failed\n")
                            self.verify_failed()  # type: ignore
                    else:
                        self.verify_failed()  # type: ignore

                elif current_state == "brainstorming":
                    context = self._get_context_content()
                    # Include any queued ideas in the brainstorming prompt
                    base_prompt = build_brainstorming_prompt(
                        roadmap_content=context["roadmap_content"],
                        engineering_plan_content=context["engineering_plan_content"],
                        task_name_content=context["task_name_content"],
                        queued_ideas=self.idea_queue if self.idea_queue else None,
                    )
                    prompt = self.prompt_customization.apply_to_prompt("brainstorming", base_prompt)
                    success = await self.run_phase(prompt, "brainstorming")
                    # Clear ideas after they've been processed
                    if self.idea_queue and success and self.on_ideas_processed:
                        self.on_ideas_processed(self.project.path)

                    self.idea_queue = []

                    if success:
                        self._check_task_name_file()

                    if self._cancelled:
                        break
                    self.brainstorm_complete()  # type: ignore

                elif current_state == "committing":
                    context = self._get_context_content()
                    base_prompt_template = build_committing_prompt(self.project.branch)
                    base_prompt = base_prompt_template.format(**context)
                    prompt = self.prompt_customization.apply_to_prompt("committing", base_prompt)
                    success = await self.run_phase(prompt, "committing")
                    if self._cancelled:
                        break

                    if success:
                        if self.project.current_feature:
                            self.project.completed_features.append(self.project.current_feature)
                            # We don't clear current_feature here, it will be updated/cleared in next planning/brainstorming check  # noqa: E501
                            # But technically it is "done".

                        # Check if there are more features
                        self.workflow_state.iteration_count += 1
                        self.project.iteration_count = self.workflow_state.iteration_count
                        iteration += 1

                        if iteration >= max_iterations:
                            self._emit_output(
                                f"\n[INFO] Max iterations ({max_iterations}) reached\n"
                            )
                            self.no_more_features()  # type: ignore
                        else:
                            self.commit_complete()  # type: ignore

                elif current_state == "error":
                    self._emit_output("\n[ERROR] Workflow is in error state. Resetting...\n")
                    await asyncio.sleep(5)
                    self.reset()  # type: ignore

                elif current_state == "completed":
                    self._emit_output("\n[DONE] Workflow completed! Restarting...\n")
                    # Restart to planning phase
                    self.restart()  # type: ignore
                    # Reset iteration count for the new cycle
                    iteration = 0
                    continue

                else:
                    self._emit_output(f"\n[UNKNOWN] Unknown state: {current_state}\n")
                    break

        finally:
            self._running = False

    def cancel(self) -> None:
        """Cancel the running workflow."""
        self._cancelled = True

    def reset_workflow(self) -> None:
        """
        Force reset the workflow to IDLE state.

        This is useful for recovering from stuck states or clearing
        the current task to start over.
        """
        if self._running:
            self.cancel()

        # Force state to idle via internal machine manipulation if needed,
        # or just set it and let the persistence handle it.
        # Since pytransitions is used, we should use to_idle() if it exists
        # (which it should as 'idle' is a state), but to_idle() might not trigger
        # all callbacks if not defined as a transition.
        # However, we can just force it.

        self.workflow_state.current_state = "idle"
        self.workflow_state.current_feature = None
        # We don't clear completed/failed history
        self.workflow_state.save()

        # Update machine state
        self.machine.set_state("idle")

        # Update project status
        self.project.status = ProjectStatus.IDLE
        self.project.current_feature = None

        logger.info("Workflow forced reset to IDLE")

        # Notify UI
        if self.on_state_change:
            self.on_state_change("reset", "idle")

    def is_running(self) -> bool:
        """Check if the workflow is currently running."""
        return self._running

    def get_diagram_source(self) -> str:
        """
        Get the state machine diagram in DOT format.

        Returns:
            DOT format string for Graphviz visualization
        """
        # Build DOT format manually since transitions may not have GraphMachine installed
        lines = ["digraph workflow {", "    rankdir=LR;", "    node [shape=box];"]

        # Highlight current state
        for state in self.states:
            if state == self.state:  # type: ignore
                lines.append(f"    {state} [style=filled, fillcolor=lightblue];")
            else:
                lines.append(f"    {state};")

        # Add transitions
        for t in self.transitions:
            source = t["source"]
            dest = t["dest"]
            trigger = t["trigger"]
            if source == "*":
                for s in self.states:
                    if s != dest:
                        lines.append(f'    {s} -> {dest} [label="{trigger}", style=dashed];')
            else:
                lines.append(f'    {source} -> {dest} [label="{trigger}"];')

        lines.append("}")
        return "\n".join(lines)

    def get_ascii_diagram(self) -> str:
        """
        Get a simple ASCII representation of the workflow.

        Returns:
            ASCII diagram string
        """
        current = self.state  # type: ignore

        diagram = """
  IDLE ──> PLANNING ──> IMPLEMENTING
    ^          │              │
    │       (fail)            v
    │          v          VERIFYING
    └───── ERROR              │
                              v
                        BRAINSTORMING
                              │
                              v
           COMMITTING <───────┘
               │
               v
           COMPLETED
               │
               v
           PLANNING (Loop)
"""

        # Add current state indicator
        state_display = current.upper() if current else "UNKNOWN"
        header = f"═══ Current: [{state_display}] ═══\n"

        return header + diagram
