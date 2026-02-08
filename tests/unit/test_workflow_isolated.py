"""Isolated unit tests for ProjectWorkflow using mocked dependencies."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from agent_pump.backends.base import AgentBackend
from agent_pump.events.bus import EventBus
from agent_pump.models.project import Project, ProjectStatus
from agent_pump.orchestrator.interfaces import (
    CheckpointManager,
    PromptLoaderService,
    TokenCountingService,
    VerificationRunner,
)
from agent_pump.orchestrator.workflow import ProjectWorkflow


class MockBackend(AgentBackend):
    """Mock backend for testing."""

    @property
    def name(self) -> str:
        return "Mock Backend"

    def run(self, *args, **kwargs):
        pass


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
    # Add config attribute
    project.config = MagicMock()
    return project


@pytest.fixture
def mock_backend():
    """Create a mock backend."""
    backend = MagicMock(spec=AgentBackend)
    backend.name = "Mock Backend"

    async def _run(*args, **kwargs):
        yield "Output line 1"
        yield "Output line 2"

    backend.run.side_effect = _run
    return backend


@pytest.fixture
def mock_event_bus():
    """Create a mock event bus."""
    return MagicMock(spec=EventBus)


@pytest.fixture
def mock_prompt_loader():
    """Create a mock prompt loader."""
    loader = MagicMock(spec=PromptLoaderService)
    loader.build_prompt = AsyncMock(return_value="Mock Prompt")
    return loader


@pytest.fixture
def mock_verification_executor():
    """Create a mock verification executor."""
    executor = MagicMock(spec=VerificationRunner)
    executor.run_all = AsyncMock(return_value={})
    return executor


@pytest.fixture
def mock_checkpoint_service():
    """Create a mock checkpoint service."""
    service = MagicMock(spec=CheckpointManager)
    service.create_checkpoint = MagicMock()
    return service


@pytest.fixture
def mock_token_counter():
    """Create a mock token counter."""
    counter = MagicMock(spec=TokenCountingService)
    counter.count_tokens = MagicMock(return_value=100)
    return counter


class TestProjectWorkflowIsolated:
    """Tests for ProjectWorkflow with injected dependencies."""

    @pytest.mark.asyncio
    async def test_initialization(
        self,
        mock_project,
        mock_backend,
        mock_event_bus,
        mock_prompt_loader,
        mock_verification_executor,
        mock_checkpoint_service,
        mock_token_counter,
    ):
        """Test that workflow initializes correctly with injected dependencies."""
        workflow = ProjectWorkflow(
            project=mock_project,
            backend=mock_backend,
            event_bus=mock_event_bus,
            prompt_loader=mock_prompt_loader,
            verification_executor=mock_verification_executor,
            checkpoint_service=mock_checkpoint_service,
            token_counter_service=mock_token_counter,
        )

        assert workflow.prompt_loader == mock_prompt_loader
        assert workflow.verification_executor == mock_verification_executor
        assert workflow.checkpoint_service == mock_checkpoint_service
        assert workflow.token_counter_service == mock_token_counter

    @pytest.mark.asyncio
    async def test_run_phase_success(
        self,
        mock_project,
        mock_backend,
        mock_token_counter,
    ):
        """Test running a phase successfully."""
        workflow = ProjectWorkflow(
            project=mock_project,
            backend=mock_backend,
            token_counter_service=mock_token_counter,
        )

        # Mock emit output to avoid errors
        workflow._emit_output = MagicMock()

        success = await workflow.run_phase("Test Prompt", "planning")

        assert success
        # Verify token counter was called
        mock_token_counter.count_tokens.assert_called()
        # Verify backend was run
        mock_backend.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_phase_failure(
        self,
        mock_project,
        mock_backend,
        mock_token_counter,
    ):
        """Test running a phase that fails (e.g. backend error)."""
        # Make backend raise an exception
        async def _run_error(*args, **kwargs):
            raise Exception("Backend Error")
            yield "Should not be reached"

        mock_backend.run.side_effect = _run_error

        workflow = ProjectWorkflow(
            project=mock_project,
            backend=mock_backend,
            token_counter_service=mock_token_counter,
        )
        workflow._emit_output = MagicMock()

        success = await workflow.run_phase("Test Prompt", "planning")

        assert not success
        mock_backend.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_prepare_phase_planning(
        self,
        mock_project,
        mock_prompt_loader,
        mock_token_counter,
    ):
        """Test preparation logic for planning phase."""
        workflow = ProjectWorkflow(
            project=mock_project,
            prompt_loader=mock_prompt_loader,
            token_counter_service=mock_token_counter,
        )
        workflow._emit_output = MagicMock()

        # Mock _read_file_content to return empty task name
        workflow._read_file_content = AsyncMock(side_effect=lambda f: "(File not found or empty)")

        # We need to mock RoadmapParser or the file system for auto-picking logic
        # Since logic inside _prepare_planning_phase instantiates RoadmapParser directly,
        # we might still need to mock that if we want to test auto-picking.
        # But here let's just ensure it runs without crashing.

        context = {}
        await workflow._prepare_phase("planning", context)

        # It should have tried to read TASK_NAME
        workflow._read_file_content.assert_any_call("TASK_NAME")
