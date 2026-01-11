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
from agent_pump.models.workspace import PhaseBackends, PromptCustomization
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

    async def run(
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
    ]

    def __init__(
        self,
        project: Project,
        backend: AgentBackend | None = None,
        config: Any | None = None,  # Avoid circular import, typed as Any but expects Config
        phase_backends: PhaseBackends | None = None,
        prompt_customization: PromptCustomization | None = None,
        idea_queue: list[str] | None = None,
        on_output: Callable[[str], None] | None = None,
        on_state_change: Callable[[str, str], None] | None = None,
        on_ideas_processed: Callable[[Path], None] | None = None,
    ):
        """
        Initialize the workflow for a project.

        Args:
            project: The project to manage
            backend: The AI agent backend to use (defaults to GeminiBackend)
            config: The full application configuration
            phase_backends: Optional phase-specific backend configuration
            prompt_customization: Optional per-phase prompt prefix/suffix overrides
            idea_queue: Optional list of ideas to include in brainstorming
            on_output: Callback for agent output lines
            on_state_change: Callback for state changes (old_state, new_state)
            on_ideas_processed: Callback when ideas have been processed
        """
        self.project = project
        self.backend = backend or GeminiBackend()
        self.config = config
        self.phase_backends = phase_backends
        self.prompt_customization = prompt_customization or PromptCustomization()
        self.idea_queue = idea_queue or []
        self.on_output = on_output
        self.on_state_change = on_state_change
        self.on_ideas_processed = on_ideas_processed
        self._running = False
        self._cancelled = False

        # Initialize verification executor with project's verification config
        self.verification_executor = VerificationExecutor(
            project_path=project.path,
            config=project.config
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

    def _after_state_change(self, *args: Any, **kwargs: Any) -> None:
        """Called after each state change."""
        old_state = self.workflow_state.current_state
        new_state = self.state  # type: ignore

        # Update workflow state
        self.workflow_state.current_state = new_state
        self.workflow_state.last_updated = datetime.now()

        # Update project status
        try:
            self.project.status = ProjectStatus(new_state)
        except ValueError:
            pass

        # Save state
        self.workflow_state.save()

        # Notify callback
        if self.on_state_change:
            self.on_state_change(old_state, new_state)

        logger.info(f"State changed: {old_state} -> {new_state}")

    def _emit_output(self, line: str) -> None:
        """Emit output line to callback."""
        if self.on_output:
            self.on_output(line)

    def _get_backend_for_phase(self, phase: str) -> BackendRunner:
        """
        Get the backend(s) to use for a specific phase.

        Args:
            phase: Phase name (planning, implementing, verifying, brainstorming, committing)

        Returns:
            AgentBackend or FallbackBackendRunner for the phase
        """
        if self.phase_backends is None:
            return self.backend

        phase_config = getattr(self.phase_backends, phase, None)
        if phase_config is None or len(phase_config.backends) == 0:
            return self.backend

        # Single backend - no fallback needed, but still use from_config for args
        if len(phase_config.backends) == 1:
            instance = phase_config.backends[0]
            try:
                backend = get_backend(instance.name)
                # If there are args, wrap in a simple way to pass them
                if instance.args:
                    # Store args to pass through during run
                    backend._extra_args = instance.args  # type: ignore
                return backend
            except ValueError:
                logger.warning(f"Unknown backend '{instance.name}', using default")
                return self.backend

        # Multiple backends - create fallback runner with args
        try:
            return create_fallback_runner_from_config(phase_config.backends)
        except ValueError as e:
            logger.warning(f"Failed to create fallback runner: {e}, using default")
            return self.backend

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
        self._emit_output(f"\n{'='*60}\n")
        self._emit_output(f"Starting {phase_name} phase...\n")
        self._emit_output(f"{'='*60}\n\n")

        start_time = datetime.now()
        output_lines: list[str] = []
        success = True

        # Get the backend for this phase
        backend = self._get_backend_for_phase(phase_name)

        # Determine timeout:
        # 1. Start with global default (1800s / 30m)
        timeout = 1800
        if self.config and hasattr(self.config, "workflow"):
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

        except Exception as e:
            logger.exception(f"Error in {phase_name} phase")
            self._emit_output(f"\n[ERROR] {e}\n")
            success = False

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # specific check for min execution time
        if success and not self._cancelled:
            if duration < self.project.min_execution_time_seconds:
                self._emit_output(f"\n[ERROR] Backend execution too short ({duration:.1f}s < {self.project.min_execution_time_seconds}s). Assuming failure.\n")
                success = False

        # Fail if no output received and not cancelled
        if not output_lines and success and not self._cancelled:
            self._emit_output("\n[ERROR] No output received from backend\n")
            success = False

        # Log phase completion
        summary = "".join(output_lines[-10:]) if output_lines else None
        self.workflow_state.log_phase_complete(success, summary)
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
                    base_prompt = build_planning_prompt(self.project.branch)
                    prompt = self.prompt_customization.apply_to_prompt("planning", base_prompt)
                    success = await self.run_phase(prompt, "planning")
                    if self._cancelled:
                        break
                    if success:
                        self.plan_complete()  # type: ignore
                    else:
                        self.plan_failed()  # type: ignore

                elif current_state == "implementing":
                    base_prompt = build_implementing_prompt(self.project.branch)
                    prompt = self.prompt_customization.apply_to_prompt("implementing", base_prompt)
                    success = await self.run_phase(prompt, "implementing")
                    if self._cancelled:
                        break
                    if success:
                        self.implement_complete()  # type: ignore
                    else:
                        self.implement_failed()  # type: ignore

                elif current_state == "verifying":
                    # First run the AI verification phase
                    base_prompt = build_verifying_prompt(self.project.branch)
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
                            self._emit_output(f"\n[{status}] {cmd_type.upper()} command: {result.command or 'N/A'}")
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
                    # Include any queued ideas in the brainstorming prompt
                    base_prompt = build_brainstorming_prompt(self.idea_queue if self.idea_queue else None)
                    prompt = self.prompt_customization.apply_to_prompt("brainstorming", base_prompt)
                    success = await self.run_phase(prompt, "brainstorming")
                    # Clear ideas after they've been processed
                    if self.idea_queue and success and self.on_ideas_processed:
                        self.on_ideas_processed(self.project.path)

                    self.idea_queue = []
                    if self._cancelled:
                        break
                    self.brainstorm_complete()  # type: ignore

                elif current_state == "committing":
                    base_prompt = build_committing_prompt(self.project.branch)
                    prompt = self.prompt_customization.apply_to_prompt("committing", base_prompt)
                    success = await self.run_phase(prompt, "committing")
                    if self._cancelled:
                        break

                    # Check if there are more features
                    # For now, always continue; the brainstorm phase will indicate if done
                    self.workflow_state.iteration_count += 1
                    self.project.iteration_count = self.workflow_state.iteration_count
                    iteration += 1

                    if iteration >= max_iterations:
                        self._emit_output(f"\n[INFO] Max iterations ({max_iterations}) reached\n")
                        self.no_more_features()  # type: ignore
                    else:
                        self.commit_complete()  # type: ignore

                elif current_state == "error":
                    self._emit_output("\n[ERROR] Workflow is in error state. Resetting...\n")
                    await asyncio.sleep(5)
                    self.reset()  # type: ignore

                elif current_state == "completed":
                    self._emit_output("\n[DONE] Workflow completed!\n")
                    break

                else:
                    self._emit_output(f"\n[UNKNOWN] Unknown state: {current_state}\n")
                    break

        finally:
            self._running = False

    def cancel(self) -> None:
        """Cancel the running workflow."""
        self._cancelled = True

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
        lines = ["digraph workflow {", '    rankdir=LR;', '    node [shape=box];']

        # Highlight current state
        for state in self.states:
            if state == self.state:  # type: ignore
                lines.append(f'    {state} [style=filled, fillcolor=lightblue];')
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
    │       (fail)            │
    │          v              v
    └───── ERROR        BRAINSTORMING
                              │
                              v
           COMMITTING <───────┘
               │
               v
           COMPLETED
"""

        # Add current state indicator
        state_display = current.upper() if current else "UNKNOWN"
        header = f"═══ Current: [{state_display}] ═══\n"

        return header + diagram
