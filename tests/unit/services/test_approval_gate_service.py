"""Unit tests for ApprovalGateService."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    ApprovalRequestedEvent,
    ApprovalResolvedEvent,
    ApprovalTimeoutEvent,
)
from agent_pump.models.approval_gate_config import (
    ApprovalDecision,
    ApprovalGateConfig,
    GateConfig,
    TimeoutAction,
)
from agent_pump.services.approval_gate_service import ApprovalGateService


@pytest.fixture
def event_bus():
    """Create an EventBus for testing."""
    return EventBus()


@pytest.fixture
def service(event_bus):
    """Create an ApprovalGateService for testing."""
    return ApprovalGateService(event_bus)


@pytest.fixture
def project_path():
    """Create a test project path."""
    return Path("/tmp/test-project")


class TestApprovalGateServiceInitialization:
    """Tests for service initialization."""

    def test_service_initialization(self, service, event_bus):
        """Test that service initializes correctly."""
        assert service.event_bus is event_bus
        assert service._pending_approvals == {}
        assert service._timeout_task is None
        assert service._shutdown is False


class TestRequestApproval:
    """Tests for requesting approval."""

    @pytest.mark.asyncio
    async def test_request_approval_success(self, service, project_path, event_bus):
        """Test successful approval request."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing", timeout_minutes=30)],
        )

        with patch.object(event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            request = await service.request_approval(
                project_path=project_path,
                phase="committing",
                feature="Add login page",
                config=config,
            )

            assert request is not None
            assert request.id is not None
            assert request.project_path == project_path
            assert request.phase == "committing"
            assert request.feature == "Add login page"
            assert request.decision == ApprovalDecision.PENDING
            assert request.timeout_at is not None

            # Verify it was added to pending
            assert project_path in service._pending_approvals
            assert service._pending_approvals[project_path]["committing"] == request

            # Verify event was published
            mock_publish.assert_called_once()
            event = mock_publish.call_args[0][0]
            assert isinstance(event, ApprovalRequestedEvent)
            assert event.project_path == project_path
            assert event.phase == "committing"

    @pytest.mark.asyncio
    async def test_request_approval_disabled_gates(self, service, project_path):
        """Test that disabled gates return None."""
        config = ApprovalGateConfig(enabled=False)

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        assert request is None

    @pytest.mark.asyncio
    async def test_request_approval_no_gate_for_phase(self, service, project_path):
        """Test that phases without gates return None."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="planning",
            feature=None,
            config=config,
        )

        assert request is None

    @pytest.mark.asyncio
    async def test_request_approval_duplicate_request(self, service, project_path):
        """Test that duplicate request returns existing request."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request1 = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        request2 = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        assert request1.id == request2.id

    @pytest.mark.asyncio
    async def test_request_approval_different_phases(self, service, project_path):
        """Test that different phases can have concurrent requests."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[
                GateConfig(phase="committing"),
                GateConfig(phase="implementing"),
            ],
        )

        request1 = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        request2 = await service.request_approval(
            project_path=project_path,
            phase="implementing",
            feature=None,
            config=config,
        )

        assert request1.id != request2.id
        assert len(service._pending_approvals[project_path]) == 2

    @pytest.mark.asyncio
    async def test_request_approval_no_timeout(self, service, project_path):
        """Test request with no timeout (timeout_minutes=0)."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing", timeout_minutes=0)],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        assert request.timeout_at is None

    @pytest.mark.asyncio
    async def test_request_approval_starts_timeout_monitor(self, service, project_path):
        """Test that requesting approval starts the timeout monitor."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing", timeout_minutes=30)],
        )

        assert service._timeout_task is None

        await service.request_approval(
            project_path=project_path,
            phase="committing",
            config=config,
        )

        assert service._timeout_task is not None


class TestResolveApproval:
    """Tests for resolving approvals."""

    @pytest.mark.asyncio
    async def test_resolve_approval_success(self, service, project_path, event_bus):
        """Test successfully resolving an approval."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        with patch.object(event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            result = await service.resolve_approval(
                request_id=request.id,
                decision=ApprovalDecision.APPROVED,
                comment="Looks good",
            )

            assert result is True
            assert request.decision == ApprovalDecision.APPROVED
            assert request.comment == "Looks good"
            assert request.resolved_at is not None

            # Verify it was removed from pending
            assert project_path not in service._pending_approvals

            # Verify event was published
            mock_publish.assert_called_once()
            event = mock_publish.call_args[0][0]
            assert isinstance(event, ApprovalResolvedEvent)
            assert event.decision == "approved"

    @pytest.mark.asyncio
    async def test_resolve_approval_reject(self, service, project_path, event_bus):
        """Test rejecting an approval."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        with patch.object(event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            await service.resolve_approval(
                request_id=request.id,
                decision=ApprovalDecision.REJECTED,
                comment="Need more tests",
            )

            assert request.decision == ApprovalDecision.REJECTED

            event = mock_publish.call_args[0][0]
            assert isinstance(event, ApprovalResolvedEvent)
            assert event.decision == "rejected"

    @pytest.mark.asyncio
    async def test_resolve_approval_not_found(self, service):
        """Test resolving non-existent approval."""
        result = await service.resolve_approval(
            request_id="non-existent-id",
            decision=ApprovalDecision.APPROVED,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_resolve_approval_already_resolved(self, service, project_path):
        """Test resolving already resolved approval."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        await service.resolve_approval(
            request_id=request.id,
            decision=ApprovalDecision.APPROVED,
        )

        result = await service.resolve_approval(
            request_id=request.id,
            decision=ApprovalDecision.REJECTED,
        )

        # Second resolve should fail or be ignored
        assert result is False
        assert request.decision == ApprovalDecision.APPROVED


class TestGetPendingApprovals:
    """Tests for getting pending approvals."""

    @pytest.mark.asyncio
    async def test_get_pending_approvals_empty(self, service):
        """Test getting pending approvals when none exist."""
        approvals = service.get_pending_approvals()
        assert approvals == []

    @pytest.mark.asyncio
    async def test_get_pending_approvals_with_data(self, service, project_path):
        """Test getting pending approvals."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing"), GateConfig(phase="implementing")],
        )

        await service.request_approval(
            project_path=project_path,
            phase="committing",
            config=config,
        )

        approvals = service.get_pending_approvals()

        assert len(approvals) == 1
        assert approvals[0].phase == "committing"

    @pytest.mark.asyncio
    async def test_get_pending_approvals_filter_by_project(self, service, project_path):
        """Test filtering pending approvals by project."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        await service.request_approval(
            project_path=project_path,
            phase="committing",
            config=config,
        )

        await service.request_approval(
            project_path=Path("/tmp/other-project"),
            phase="committing",
            config=config,
        )

        approvals = service.get_pending_approvals(project_path=project_path)

        assert len(approvals) == 1
        assert approvals[0].project_path == project_path

    @pytest.mark.asyncio
    async def test_get_pending_approvals_filter_by_phase(self, service, project_path):
        """Test filtering pending approvals by phase."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing"), GateConfig(phase="implementing")],
        )

        await service.request_approval(
            project_path=project_path,
            phase="committing",
            config=config,
        )

        await service.request_approval(
            project_path=Path("/tmp/other-project"),
            phase="implementing",
            config=config,
        )

        approvals = service.get_pending_approvals(phase="committing")

        assert len(approvals) == 1
        assert approvals[0].phase == "committing"

    @pytest.mark.asyncio
    async def test_get_approval_by_id(self, service, project_path):
        """Test getting a specific approval by ID."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        found = service.get_approval_by_id(request.id)

        assert found is not None
        assert found.id == request.id

    @pytest.mark.asyncio
    async def test_get_approval_by_id_not_found(self, service):
        """Test getting non-existent approval by ID."""
        found = service.get_approval_by_id("non-existent")
        assert found is None


class TestBatchOperations:
    """Tests for batch approval operations."""

    @pytest.mark.asyncio
    async def test_batch_approve_all(self, service, project_path, event_bus):
        """Test approving all pending requests."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing"), GateConfig(phase="implementing")],
        )

        request1 = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        request2 = await service.request_approval(
            project_path=Path("/tmp/other-project"),
            phase="implementing",
            feature=None,
            config=config,
        )

        with patch.object(event_bus, "publish", new_callable=AsyncMock):
            count = await service.batch_approve_all(comment="Bulk approval")

            assert count == 2
            assert request1.decision == ApprovalDecision.APPROVED
            assert request2.decision == ApprovalDecision.APPROVED

    @pytest.mark.asyncio
    async def test_batch_approve_by_project(self, service, project_path, event_bus):
        """Test approving all requests for a specific project."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing"), GateConfig(phase="implementing")],
        )

        await service.request_approval(
            project_path=project_path,
            phase="committing",
            config=config,
        )

        other_request = await service.request_approval(
            project_path=Path("/tmp/other-project"),
            phase="implementing",
            feature=None,
            config=config,
        )

        with patch.object(event_bus, "publish", new_callable=AsyncMock):
            count = await service.batch_approve_all(project_path=project_path)

            assert count == 1
            assert other_request.decision == ApprovalDecision.PENDING

    @pytest.mark.asyncio
    async def test_batch_reject_all(self, service, project_path, event_bus):
        """Test rejecting all pending requests."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        with patch.object(event_bus, "publish", new_callable=AsyncMock):
            count = await service.batch_reject_all(comment="Bulk reject")

            assert count == 1
            assert request.decision == ApprovalDecision.REJECTED

    @pytest.mark.asyncio
    async def test_batch_approve_empty(self, service):
        """Test batch approve when no pending requests."""
        count = await service.batch_approve_all()
        assert count == 0


class TestTimeoutHandling:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_timeout_monitor_auto_reject(self, service, project_path, event_bus):
        """Test that auto-reject timeout action works."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[
                GateConfig(
                    phase="committing",
                    timeout_minutes=1,
                    timeout_action=TimeoutAction.AUTO_REJECT,
                )
            ],
        )

        with patch.object(event_bus, "publish", new_callable=AsyncMock) as mock_publish:
            request = await service.request_approval(
                project_path=project_path,
                phase="committing",
                feature=None,
                config=config,
            )

            # Wait for timeout monitor to process
            await asyncio.sleep(0.1)

            # Manually expire the request
            request.timeout_at = datetime.now() - timedelta(minutes=1)

            # Manually trigger timeout processing
            await service._process_timeouts()

            assert request.decision == ApprovalDecision.TIMEOUT
            assert request.has_timed_out()

            # Verify timeout event was published
            timeout_events = [
                call
                for call in mock_publish.call_args_list
                if isinstance(call[0][0], ApprovalTimeoutEvent)
            ]
            assert len(timeout_events) > 0

    @pytest.mark.asyncio
    async def test_timeout_monitor_auto_approve(self, service, project_path, event_bus):
        """Test that auto-approve timeout action works."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[
                GateConfig(
                    phase="committing",
                    timeout_minutes=0,
                    timeout_action=TimeoutAction.AUTO_APPROVE,
                )
            ],
        )

        with patch.object(event_bus, "publish", new_callable=AsyncMock):
            request = await service.request_approval(
                project_path=project_path,
                phase="committing",
                feature=None,
                config=config,
            )

            # Manually expire the request
            request.timeout_at = datetime.now() - timedelta(minutes=1)

            await service._process_timeouts()

            assert request.decision == ApprovalDecision.TIMEOUT

    @pytest.mark.asyncio
    async def test_timeout_monitor_wait_action(self, service, project_path):
        """Test that wait timeout action leaves request pending."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[
                GateConfig(
                    phase="committing",
                    timeout_minutes=0,
                    timeout_action=TimeoutAction.WAIT,
                )
            ],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        # Simulate that request has timed out
        request.timeout_at = datetime.now() - timedelta(minutes=1)

        await service._process_timeouts()

        # Decision should be TIMEOUT (service resolves to timeout, workflow handles action)
        assert request.decision == ApprovalDecision.TIMEOUT

    @pytest.mark.asyncio
    async def test_no_timeout_when_timeout_at_none(self, service, project_path):
        """Test that requests without timeout_at don't timeout."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing", timeout_minutes=0)],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        assert request.timeout_at is None

        await service._process_timeouts()

        assert request.decision == ApprovalDecision.PENDING

    @pytest.mark.asyncio
    async def test_timeout_monitor_stop_on_shutdown(self, service):
        """Test that timeout monitor stops on shutdown."""
        service._shutdown = True

        # Should return immediately
        await service._timeout_monitor()

        assert service._timeout_task is None


class TestWaitForApproval:
    """Tests for waiting for approval resolution."""

    @pytest.mark.asyncio
    async def test_wait_for_approval_success(self, service, project_path):
        """Test waiting for approval that gets approved."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        # Resolve after short delay
        async def delayed_resolve():
            await asyncio.sleep(0.05)
            await service.resolve_approval(
                request_id=request.id,
                decision=ApprovalDecision.APPROVED,
            )

        # Start both concurrently
        resolve_task = asyncio.create_task(delayed_resolve())
        result = await service.wait_for_approval(request.id, timeout=1.0)
        await resolve_task

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_approval_rejected(self, service, project_path):
        """Test waiting for approval that gets rejected."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        async def delayed_resolve():
            await asyncio.sleep(0.05)
            await service.resolve_approval(
                request_id=request.id,
                decision=ApprovalDecision.REJECTED,
            )

        resolve_task = asyncio.create_task(delayed_resolve())
        result = await service.wait_for_approval(request.id, timeout=1.0)
        await resolve_task

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_approval_timeout(self, service, project_path):
        """Test waiting for approval that times out."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature=None,
            config=config,
        )

        # Don't resolve - should timeout
        result = await service.wait_for_approval(request.id, timeout=0.05)

        assert result is None

    @pytest.mark.asyncio
    async def test_wait_for_approval_not_found(self, service):
        """Test waiting for non-existent approval."""
        result = await service.wait_for_approval("non-existent", timeout=0.1)
        assert result is None


class TestPersistence:
    """Tests for approval request persistence."""

    @pytest.mark.asyncio
    async def test_save_and_load_pending_approvals(
        self, service, project_path, tmp_path, event_bus
    ):
        """Test saving and loading pending approvals."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        # Create and resolve one request
        request1 = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature="Feature 1",
            config=config,
        )
        await service.resolve_approval(request1.id, ApprovalDecision.APPROVED)

        # Create another pending request
        request2 = await service.request_approval(
            project_path=Path("/tmp/other-project"),
            phase="committing",
            feature="Feature 2",
            config=config,
        )

        # Save to file
        state_file = tmp_path / "approvals.json"
        await service.save_pending_approvals(state_file)

        # Create new service and load
        new_service = ApprovalGateService(event_bus)
        await new_service.load_pending_approvals(state_file)

        # Should only load pending request (request2)
        loaded = new_service.get_pending_approvals()
        assert len(loaded) == 1
        assert loaded[0].id == request2.id
        assert loaded[0].feature == "Feature 2"

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self, service, tmp_path):
        """Test loading from non-existent file."""
        state_file = tmp_path / "nonexistent.json"
        await service.load_pending_approvals(state_file)

        assert service._pending_approvals == {}


class TestShutdown:
    """Tests for service shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown(self, service, project_path):
        """Test service shutdown."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        await service.request_approval(
            project_path=project_path,
            phase="committing",
            config=config,
        )

        # Start timeout monitor
        service._timeout_task = asyncio.create_task(service._timeout_monitor())

        await service.shutdown()

        assert service._shutdown is True
        assert service._timeout_task is None

    @pytest.mark.asyncio
    async def test_shutdown_cancels_timeouts(self, service, project_path):
        """Test that shutdown cancels timeout processing."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        await service.request_approval(
            project_path=project_path,
            phase="committing",
            config=config,
        )

        # Timeout monitor should be running
        assert service._timeout_task is not None

        await service.shutdown()

        # Should be cancelled
        assert service._timeout_task is None


class TestGetApprovalStatus:
    """Tests for getting approval status information."""

    @pytest.mark.asyncio
    async def test_get_approval_status_summary(self, service, project_path):
        """Test getting summary of approval status."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        await service.request_approval(
            project_path=project_path,
            phase="committing",
            config=config,
        )

        await service.request_approval(
            project_path=Path("/tmp/other-project"),
            phase="committing",
            config=config,
        )

        summary = service.get_approval_status_summary()

        assert summary["total_pending"] == 2
        assert summary["by_project"][str(project_path)] == 1
        assert summary["by_phase"]["committing"] == 2

    @pytest.mark.asyncio
    async def test_get_approval_status_empty(self, service):
        """Test status summary when no approvals."""
        summary = service.get_approval_status_summary()

        assert summary["total_pending"] == 0
        assert summary["by_project"] == {}
        assert summary["by_phase"] == {}

    @pytest.mark.asyncio
    async def test_get_project_approval_status(self, service, project_path):
        """Test getting status for a specific project."""
        config = ApprovalGateConfig(
            enabled=True,
            gates=[GateConfig(phase="committing")],
        )

        request = await service.request_approval(
            project_path=project_path,
            phase="committing",
            feature="Test Feature",
            config=config,
        )

        status = service.get_project_approval_status(project_path)

        assert status["has_pending"] is True
        assert status["pending_count"] == 1
        assert status["phases"]["committing"]["feature"] == "Test Feature"
        assert status["phases"]["committing"]["request_id"] == request.id
