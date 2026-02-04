"""Service for managing custom workflow definitions.

This service provides validation, import/export, and CRUD operations
for custom workflow definitions stored in workspace configuration.
"""

import json
import logging
from pathlib import Path

import yaml

from agent_pump.models.workspace import Workspace
from agent_pump.orchestrator.workflow_definition import WorkflowDefinition, WorkflowPhase

logger = logging.getLogger(__name__)


class WorkflowValidationError(Exception):
    """Raised when workflow validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Workflow validation failed: {'; '.join(errors)}")


class WorkflowEditorService:
    """Service for editing and managing custom workflow definitions."""

    def __init__(self, workspace: Workspace):
        """Initialize with a workspace.

        Args:
            workspace: The workspace to store/retrieve workflows from.
        """
        self.workspace = workspace

    def validate_workflow(self, workflow: WorkflowDefinition) -> list[str]:
        """Validate a workflow definition for integrity.

        Args:
            workflow: The workflow to validate.

        Returns:
            List of validation error messages. Empty if valid.
        """
        errors = []

        # Check for workflow name
        if not workflow.name or not workflow.name.strip():
            errors.append("Workflow must have a name")

        # Check for phases
        if not workflow.phases:
            errors.append("Workflow must have at least one phase")
            return errors

        # Check for duplicate phase names
        phase_names = [p.name for p in workflow.phases]
        duplicates = {name for name in phase_names if phase_names.count(name) > 1}
        if duplicates:
            errors.append(f"Duplicate phase names: {', '.join(duplicates)}")

        # Get all states in the workflow
        all_states = set(workflow.get_states())
        defined_states = {p.name for p in workflow.phases}
        defined_states.add(workflow.initial_state)
        defined_states.update(workflow.terminal_states)

        # Check for valid on_success targets
        for phase in workflow.phases:
            if not phase.on_success:
                errors.append(f"Phase '{phase.name}' must have an on_success target")
            elif phase.on_success not in all_states:
                errors.append(
                    f"Phase '{phase.name}' has invalid on_success target: '{phase.on_success}'"
                )

            # Check for valid on_failure targets (if specified)
            if phase.on_failure and phase.on_failure not in all_states:
                errors.append(
                    f"Phase '{phase.name}' has invalid on_failure target: '{phase.on_failure}'"
                )

        # Check for orphaned states (not reachable from initial state)
        reachable = self._get_reachable_states(workflow)
        orphaned = defined_states - reachable - set(workflow.terminal_states)
        if orphaned:
            errors.append(f"Unreachable states (orphaned): {', '.join(orphaned)}")

        return errors

    def _get_reachable_states(self, workflow: WorkflowDefinition) -> set[str]:
        """Get all states reachable from the initial state.

        Args:
            workflow: The workflow definition.

        Returns:
            Set of reachable state names.
        """
        reachable = {workflow.initial_state}
        transitions = workflow.get_transitions()

        # Build a simple transition graph
        changed = True
        while changed:
            changed = False
            for t in transitions:
                source = t.get("source")
                dest = t.get("dest")
                if (
                    isinstance(source, str)
                    and isinstance(dest, str)
                    and source in reachable
                    and dest not in reachable
                ):
                    reachable.add(dest)
                    changed = True

        return reachable

    def save_workflow(self, workflow: WorkflowDefinition) -> None:
        """Save a workflow to the workspace.

        Args:
            workflow: The workflow to save.

        Raises:
            WorkflowValidationError: If workflow fails validation.
        """
        errors = self.validate_workflow(workflow)
        if errors:
            raise WorkflowValidationError(errors)

        # Store as dict in workspace
        self.workspace.workflow_definitions[workflow.name] = workflow.model_dump()
        self.workspace.save()
        logger.info(f"Saved workflow '{workflow.name}' to workspace '{self.workspace.name}'")

    def get_workflow(self, name: str) -> WorkflowDefinition | None:
        """Get a workflow by name.

        Args:
            name: The workflow name.

        Returns:
            The workflow definition, or None if not found.
        """
        if name == "default":
            from agent_pump.orchestrator.workflow_definition import DEFAULT_WORKFLOW

            return DEFAULT_WORKFLOW

        data = self.workspace.workflow_definitions.get(name)
        if data:
            return WorkflowDefinition.model_validate(data)
        return None

    def delete_workflow(self, name: str) -> bool:
        """Delete a workflow from the workspace.

        Args:
            name: The workflow name to delete.

        Returns:
            True if deleted, False if not found.
        """
        if name in self.workspace.workflow_definitions:
            del self.workspace.workflow_definitions[name]
            self.workspace.save()
            logger.info(f"Deleted workflow '{name}' from workspace '{self.workspace.name}'")
            return True
        return False

    def list_workflows(self) -> list[str]:
        """List all available workflow names.

        Returns:
            List of workflow names including 'default'.
        """
        names = ["default"]
        names.extend(self.workspace.workflow_definitions.keys())
        return names

    def generate_unique_name(self, base_name: str) -> str:
        """Generate a unique workflow name based on a base name.

        Args:
            base_name: The desired base name.

        Returns:
            A unique name (base_name if available, otherwise base_name_1, etc.).
        """
        if base_name not in self.workspace.workflow_definitions:
            return base_name

        counter = 1
        while f"{base_name}_{counter}" in self.workspace.workflow_definitions:
            counter += 1
        return f"{base_name}_{counter}"

    def export_to_yaml(self, workflow: WorkflowDefinition, path: Path) -> None:
        """Export a workflow to YAML file.

        Args:
            workflow: The workflow to export.
            path: The file path to export to.
        """
        data = workflow.model_dump()
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        logger.info(f"Exported workflow '{workflow.name}' to {path}")

    def export_to_json(self, workflow: WorkflowDefinition, path: Path) -> None:
        """Export a workflow to JSON file.

        Args:
            workflow: The workflow to export.
            path: The file path to export to.
        """
        data = workflow.model_dump()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported workflow '{workflow.name}' to {path}")

    def import_from_yaml(self, path: Path) -> WorkflowDefinition:
        """Import a workflow from YAML file.

        Args:
            path: The file path to import from.

        Returns:
            The imported workflow definition.

        Raises:
            WorkflowValidationError: If imported workflow is invalid.
            FileNotFoundError: If file doesn't exist.
        """
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        workflow = WorkflowDefinition.model_validate(data)
        errors = self.validate_workflow(workflow)
        if errors:
            raise WorkflowValidationError(errors)

        logger.info(f"Imported workflow '{workflow.name}' from {path}")
        return workflow

    def import_from_json(self, path: Path) -> WorkflowDefinition:
        """Import a workflow from JSON file.

        Args:
            path: The file path to import from.

        Returns:
            The imported workflow definition.

        Raises:
            WorkflowValidationError: If imported workflow is invalid.
            FileNotFoundError: If file doesn't exist.
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        workflow = WorkflowDefinition.model_validate(data)
        errors = self.validate_workflow(workflow)
        if errors:
            raise WorkflowValidationError(errors)

        logger.info(f"Imported workflow '{workflow.name}' from {path}")
        return workflow

    def create_from_template(self, template_name: str) -> WorkflowDefinition:
        """Create a new workflow from a built-in template.

        Args:
            template_name: Name of the template ('minimal', 'default', 'extended').

        Returns:
            A new workflow definition based on the template.

        Raises:
            ValueError: If template name is unknown.
        """
        if template_name == "minimal":
            return WorkflowDefinition(
                name="custom",
                description="Minimal 2-phase workflow",
                phases=[
                    WorkflowPhase(name="planning", on_success="implementing", icon="📋"),
                    WorkflowPhase(name="implementing", on_success="completed", icon="🔨"),
                ],
            )
        elif template_name == "default":
            from agent_pump.orchestrator.workflow_definition import DEFAULT_WORKFLOW

            return WorkflowDefinition.model_validate(DEFAULT_WORKFLOW.model_dump())
        elif template_name == "extended":
            return WorkflowDefinition(
                name="custom",
                description="Extended workflow with review phase",
                phases=[
                    WorkflowPhase(name="planning", on_success="implementing", icon="📋"),
                    WorkflowPhase(name="implementing", on_success="reviewing", icon="🔨"),
                    WorkflowPhase(
                        name="reviewing",
                        on_success="verifying",
                        on_failure="implementing",
                        icon="👀",
                    ),
                    WorkflowPhase(name="verifying", on_success="committing", icon="✅"),
                    WorkflowPhase(name="committing", on_success="completed", icon="📝"),
                ],
            )
        else:
            raise ValueError(f"Unknown template: {template_name}")

    def duplicate_workflow(self, name: str, new_name: str | None = None) -> WorkflowDefinition:
        """Duplicate an existing workflow.

        Args:
            name: Name of the workflow to duplicate.
            new_name: Optional new name (auto-generated if not provided).

        Returns:
            The duplicated workflow with a new name.

        Raises:
            KeyError: If source workflow not found.
        """
        source = self.get_workflow(name)
        if not source:
            raise KeyError(f"Workflow not found: {name}")

        if not new_name:
            new_name = self.generate_unique_name(f"{name}_copy")

        # Create copy with new name
        data = source.model_dump()
        data["name"] = new_name
        return WorkflowDefinition.model_validate(data)
