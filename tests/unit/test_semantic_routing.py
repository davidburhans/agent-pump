"""Unit tests for Semantic Agent-Routed Workflow Decisions."""

from unittest.mock import MagicMock

import pytest

from agent_pump.backends.base import AgentBackend
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.orchestrator.interfaces import TokenCountingService
from agent_pump.orchestrator.workflow import ProjectWorkflow
from agent_pump.orchestrator.workflow_definition import (
    RoutingChoice,
    WorkflowDefinition,
    WorkflowPhase,
    WorkflowRouting,
)


@pytest.fixture
def mock_project(tmp_path):
    """Create a mock project."""
    project = MagicMock(spec=Project)
    project.path = tmp_path
    project.name = "Test Project"
    project.status = ProjectStatus.IDLE
    project.current_feature = None
    project.completed_features = []
    project.failed_features = []
    project.min_execution_time_seconds = 0
    project.config = MagicMock()
    return project


@pytest.fixture
def mock_token_counter():
    """Create a mock token counter."""
    counter = MagicMock(spec=TokenCountingService)
    counter.count_tokens = MagicMock(return_value=100)
    return counter


class TestSemanticRoutingSchema:
    """Test cases for WorkflowDefinition extensions supporting semantic routing."""

    def test_schema_parsing(self):
        """Test that custom routing schemas parse correctly and default to None."""
        phase_without_routing = WorkflowPhase(
            name="planning",
            on_success="implementing",
            on_failure="error",
        )
        assert phase_without_routing.routing is None

        phase_with_routing = WorkflowPhase(
            name="planning",
            on_success="implementing",
            on_failure="error",
            routing=WorkflowRouting(
                type="agent",
                choices=[
                    RoutingChoice(target="implementing", description="Implement the design"),
                    RoutingChoice(target="troubleshooting", description="Troubleshoot issues"),
                ],
            ),
        )
        assert phase_with_routing.routing is not None
        assert len(phase_with_routing.routing.choices) == 2
        assert phase_with_routing.routing.choices[0].target == "implementing"

    def test_get_transitions_registers_choices(self):
        """Test that get_transitions generates f'{phase.name}_route_{choice.target}' triggers."""
        phase = WorkflowPhase(
            name="verifying",
            on_success="committing",
            on_failure="troubleshooting",
            routing=WorkflowRouting(
                choices=[
                    RoutingChoice(target="committing", description="All tests green"),
                    RoutingChoice(target="implementing", description="Test failed, rewrite code"),
                ]
            ),
        )
        wf_def = WorkflowDefinition(
            name="custom",
            initial_state="idle",
            phases=[phase],
        )

        transitions = wf_def.get_transitions()

        # Should not register default verifying_complete or verifying_failed
        triggers = [t["trigger"] for t in transitions]
        assert "verifying_complete" not in triggers
        assert "verifying_failed" not in triggers

        # Should register dynamic route-based transitions
        assert "verifying_route_committing" in triggers
        assert "verifying_route_implementing" in triggers

        # Validate transition details
        t_committing = next(t for t in transitions if t["trigger"] == "verifying_route_committing")
        assert t_committing["source"] == "verifying"
        assert t_committing["dest"] == "committing"


class TestProjectWorkflowRouting:
    """Test cases for semantic routing execution loop in ProjectWorkflow."""

    @pytest.mark.asyncio
    async def test_run_semantic_router_json_parsing(self, mock_project, mock_token_counter):
        """Test that semantic router successfully parses valid JSON responses from LLM."""
        mock_backend = MagicMock(spec=AgentBackend)
        mock_backend.name = "Mock Backend"

        # Mock JSON response from backend
        async def _run_json(*args, **kwargs):
            yield (
                '{\n  "next_step": "implementing",\n'
                '  "reason": "Test failed with compilation error."\n}'
            )

        mock_backend.run.side_effect = _run_json

        routing = WorkflowRouting(
            choices=[
                RoutingChoice(target="committing", description="All green"),
                RoutingChoice(target="implementing", description="Rewrite code"),
            ]
        )
        phase = WorkflowPhase(
            name="verifying",
            on_success="committing",
            routing=routing,
        )
        wf_def = WorkflowDefinition(
            name="custom",
            initial_state="idle",
            phases=[phase],
        )

        workflow = ProjectWorkflow(
            project=mock_project,
            backend=mock_backend,
            token_counter_service=mock_token_counter,
            workflow_def=wf_def,
        )
        workflow._emit_output = MagicMock()

        target = await workflow._run_semantic_router("verifying", ["Output line 1"])

        assert target == "implementing"

    @pytest.mark.asyncio
    async def test_run_semantic_router_regex_fallback(self, mock_project, mock_token_counter):
        """Test that semantic router falls back to regex matching if JSON output is invalid."""
        mock_backend = MagicMock(spec=AgentBackend)
        mock_backend.name = "Mock Backend"

        # Mock non-JSON text response containing target string
        async def _run_text(*args, **kwargs):
            yield (
                "The logs indicate that verification failed, so I select target"
                " 'implementing' to continue."
            )

        mock_backend.run.side_effect = _run_text

        routing = WorkflowRouting(
            choices=[
                RoutingChoice(target="committing", description="All green"),
                RoutingChoice(target="implementing", description="Rewrite code"),
            ]
        )
        phase = WorkflowPhase(
            name="verifying",
            on_success="committing",
            routing=routing,
        )
        wf_def = WorkflowDefinition(
            name="custom",
            initial_state="idle",
            phases=[phase],
        )

        workflow = ProjectWorkflow(
            project=mock_project,
            backend=mock_backend,
            token_counter_service=mock_token_counter,
            workflow_def=wf_def,
        )
        workflow._emit_output = MagicMock()

        target = await workflow._run_semantic_router("verifying", ["Output line 1"])

        # Fallback should match the target 'implementing' mentioned in text
        assert target == "implementing"

    @pytest.mark.asyncio
    async def test_run_semantic_router_invalid_fallback(
        self, mock_project, mock_token_counter
    ):
        """Test that semantic router falls back to default on_success if LLM returns invalid target.

        This ensures robust behavior when the LLM outputs garbage.
        """
        mock_backend = MagicMock(spec=AgentBackend)
        mock_backend.name = "Mock Backend"

        async def _run_invalid(*args, **kwargs):
            yield "Let's route to a completely invalid target state named 'scrapping'."

        mock_backend.run.side_effect = _run_invalid

        routing = WorkflowRouting(
            choices=[
                RoutingChoice(target="committing", description="All green"),
                RoutingChoice(target="implementing", description="Rewrite code"),
            ]
        )
        phase = WorkflowPhase(
            name="verifying",
            on_success="committing",
            routing=routing,
        )
        wf_def = WorkflowDefinition(
            name="custom",
            initial_state="idle",
            phases=[phase],
        )

        workflow = ProjectWorkflow(
            project=mock_project,
            backend=mock_backend,
            token_counter_service=mock_token_counter,
            workflow_def=wf_def,
        )
        workflow._emit_output = MagicMock()

        target = await workflow._run_semantic_router("verifying", ["Output line 1"])

        # Should fall back to default phase.on_success
        assert target == "committing"
