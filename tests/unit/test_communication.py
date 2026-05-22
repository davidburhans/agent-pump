import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_pump.communication.injection import inject_communication_config
from agent_pump.models.backend_signal import (
    BackendSignal,
    RequestInputPayload,
    SignalType,
)


def test_backend_signal_validation():
    """Test validation of BackendSignal and payload models."""
    # Test valid signal
    signal = BackendSignal(
        type=SignalType.REQUEST_INPUT,
        project_id="test_project",
        phase="planning",
        payload={
            "question": "What is next?",
            "options": ["A", "B"],
            "timeout_seconds": 60,
        },
    )
    assert signal.type == SignalType.REQUEST_INPUT
    assert signal.project_id == "test_project"

    # Test payload validation
    payload = RequestInputPayload(**signal.payload)
    assert payload.question == "What is next?"
    assert payload.options == ["A", "B"]

    # Test invalid signal (missing field)
    with pytest.raises(ValidationError):
        BackendSignal(
            type=SignalType.DECISION,
            project_id="test_project",
            # phase missing
            payload={},
        )


def test_inject_communication_config(tmp_path):
    """Test environment injection and config file creation."""
    # Mock home directory for testing config file creation
    # We can't easily mock Path.home() globally, but we can verify the return dict

    # Just verify env dict first
    env = inject_communication_config(
        project_id="my-project",
        backend_type="gemini",
        callback_url="http://localhost:8000/callback",
        mcp_port=1234,
    )

    assert env["AGENT_PUMP_CALLBACK_URL"] == "http://localhost:8000/callback"
    assert env["AGENT_PUMP_PROJECT_ID"] == "my-project"
    assert env["AGENT_PUMP_MCP_PORT"] == "1234"


def test_inject_communication_config_writes_correct_url():
    """Test that the injected config uses the correct MCP URL (/mcp/sse)."""
    from unittest.mock import MagicMock, patch

    with patch("pathlib.Path.home") as mock_home:
        mock_config_path = MagicMock()
        mock_config_path.exists.return_value = False
        mock_home.return_value.__truediv__.return_value.__truediv__.return_value = mock_config_path

        inject_communication_config(
            project_id="test",
            backend_type="gemini",
            callback_url="url",
            mcp_port=8080,
        )

        # Verify write_text was called with correct URL
        args, _ = mock_config_path.write_text.call_args
        content = json.loads(args[0])
        assert content["mcpServers"]["agent-pump"]["url"] == "http://localhost:8080/mcp/sse"


@pytest.mark.asyncio
async def test_workflow_request_input():
    import asyncio
    from unittest.mock import MagicMock

    from agent_pump.events.bus import EventBus
    from agent_pump.models.project import Project
    from agent_pump.orchestrator.workflow import ProjectWorkflow

    # Setup
    project = Project(path=Path("/tmp/test"), name="test")
    event_bus = EventBus()
    workflow = ProjectWorkflow(project=project, event_bus=event_bus)

    # Mock emit output to avoid print
    workflow._emit_output = MagicMock()

    # Simulate user response in background
    async def respond_later():
        await asyncio.sleep(0.1)
        workflow.resolve_input("User Response")

    asyncio.create_task(respond_later())

    # Call request_input
    response = await workflow.request_input("Question?", timeout=1)

    assert response == "User Response"
    assert workflow._pending_input_future is None


@pytest.mark.asyncio
async def test_workflow_request_input_timeout():
    import asyncio
    from unittest.mock import MagicMock

    from agent_pump.models.project import Project
    from agent_pump.orchestrator.workflow import ProjectWorkflow

    project = Project(path=Path("/tmp/test"), name="test")
    workflow = ProjectWorkflow(project=project)
    workflow._emit_output = MagicMock()

    with pytest.raises(asyncio.TimeoutError):
        await workflow.request_input("Question?", timeout=0.1)

    assert workflow._pending_input_future is None


@pytest.mark.asyncio
async def test_handle_request_input():
    from pathlib import Path
    from unittest.mock import AsyncMock, MagicMock

    from agent_pump.communication.callback_server import handle_request_input
    from agent_pump.models.backend_signal import BackendSignal, SignalType

    # Setup mocks
    mock_workflow = MagicMock()
    mock_workflow.request_input = AsyncMock(return_value="User says yes")

    mock_project_service = MagicMock()
    mock_project_service.workflows = {Path("/tmp/test").resolve(): mock_workflow}

    mock_request = MagicMock()
    mock_request.app.state.project_service = mock_project_service

    # Valid signal
    signal = BackendSignal(
        type=SignalType.REQUEST_INPUT,
        project_id="/tmp/test",
        phase="planning",
        payload={"question": "Are you sure?"},
    )

    response = await handle_request_input(signal, mock_request)

    assert response["status"] == "ok"
    assert response["response"] == "User says yes"
    mock_workflow.request_input.assert_awaited_with("Are you sure?", None, 300)


@pytest.mark.asyncio
async def test_handle_request_input_error():
    from unittest.mock import MagicMock

    from fastapi import HTTPException

    from agent_pump.communication.callback_server import handle_request_input
    from agent_pump.models.backend_signal import BackendSignal, SignalType

    mock_project_service = MagicMock()
    mock_project_service.workflows = {}

    mock_request = MagicMock()
    mock_request.app.state.project_service = mock_project_service

    signal = BackendSignal(
        type=SignalType.REQUEST_INPUT,
        project_id="/tmp/unknown",
        phase="planning",
        payload={"question": "?"},
    )

    with pytest.raises(HTTPException) as excinfo:
        await handle_request_input(signal, mock_request)

    assert excinfo.value.status_code == 404
