"""Unit tests for Approval Gate configuration models."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_pump.models.approval_gate_config import (
    ApprovalDecision,
    ApprovalGateConfig,
    ApprovalRequest,
    GateConfig,
    TimeoutAction,
)


class TestTimeoutAction:
    """Tests for TimeoutAction enum."""

    def test_timeout_action_values(self):
        """Test that TimeoutAction enum has correct values."""
        assert TimeoutAction.WAIT == "wait"
        assert TimeoutAction.AUTO_APPROVE == "auto_approve"
        assert TimeoutAction.AUTO_REJECT == "auto_reject"


class TestApprovalDecision:
    """Tests for ApprovalDecision enum."""

    def test_approval_decision_values(self):
        """Test that ApprovalDecision enum has correct values."""
        assert ApprovalDecision.PENDING == "pending"
        assert ApprovalDecision.APPROVED == "approved"
        assert ApprovalDecision.REJECTED == "rejected"
        assert ApprovalDecision.TIMEOUT == "timeout"


class TestGateConfig:
    """Tests for GateConfig model."""

    def test_gate_config_defaults(self):
        """Test GateConfig with default values."""
        config = GateConfig(phase="committing")
        assert config.phase == "committing"
        assert config.timeout_minutes == 30
        assert config.timeout_action == TimeoutAction.AUTO_REJECT
        assert config.require_comment is False

    def test_gate_config_custom_values(self):
        """Test GateConfig with custom values."""
        config = GateConfig(
            phase="planning",
            timeout_minutes=60,
            timeout_action=TimeoutAction.AUTO_APPROVE,
            require_comment=True,
        )
        assert config.phase == "planning"
        assert config.timeout_minutes == 60
        assert config.timeout_action == TimeoutAction.AUTO_APPROVE
        assert config.require_comment is True

    def test_gate_config_validation_timeout_minutes_negative(self):
        """Test that negative timeout_minutes raises validation error."""
        with pytest.raises(ValidationError) as excinfo:
            GateConfig(phase="committing", timeout_minutes=-1)
        assert "greater_than_equal" in str(
            excinfo.value
        ) or "Input should be greater than or equal to 0" in str(excinfo.value)

    def test_gate_config_validation_timeout_minutes_too_large(self):
        """Test that timeout_minutes > 10080 (1 week) raises validation error."""
        with pytest.raises(ValidationError) as excinfo:
            GateConfig(phase="committing", timeout_minutes=10081)
        assert "less_than_equal" in str(
            excinfo.value
        ) or "Input should be less than or equal to 10080" in str(excinfo.value)

    def test_gate_config_validation_invalid_phase(self):
        """Test that invalid phase name raises validation error."""
        with pytest.raises(ValidationError) as excinfo:
            GateConfig(phase="")
        assert "phase cannot be empty" in str(excinfo.value)


class TestApprovalGateConfig:
    """Tests for ApprovalGateConfig model."""

    def test_default_config(self):
        """Test default ApprovalGateConfig."""
        config = ApprovalGateConfig()
        assert config.enabled is False
        assert config.gates == []
        assert config.notifications.desktop is True
        assert config.notifications.timeout_warning_minutes == 5

    def test_enabled_with_gates(self):
        """Test enabled config with gates."""
        gates = [
            GateConfig(phase="committing", timeout_minutes=30),
            GateConfig(phase="implementing", timeout_minutes=60),
        ]
        config = ApprovalGateConfig(enabled=True, gates=gates)
        assert config.enabled is True
        assert len(config.gates) == 2
        assert config.gates[0].phase == "committing"
        assert config.gates[1].phase == "implementing"

    def test_get_gate_for_phase_existing(self):
        """Test getting gate config for an existing phase."""
        gates = [
            GateConfig(phase="committing"),
            GateConfig(phase="implementing"),
        ]
        config = ApprovalGateConfig(gates=gates)
        gate = config.get_gate_for_phase("committing")
        assert gate is not None
        assert gate.phase == "committing"

    def test_get_gate_for_phase_nonexistent(self):
        """Test getting gate config for a non-existent phase."""
        gates = [GateConfig(phase="committing")]
        config = ApprovalGateConfig(gates=gates)
        gate = config.get_gate_for_phase("planning")
        assert gate is None

    def test_is_phase_gated_true(self):
        """Test is_phase_gated returns True for gated phase."""
        gates = [GateConfig(phase="committing")]
        config = ApprovalGateConfig(enabled=True, gates=gates)
        assert config.is_phase_gated("committing") is True

    def test_is_phase_gated_false_when_disabled(self):
        """Test is_phase_gated returns False when gates are disabled."""
        gates = [GateConfig(phase="committing")]
        config = ApprovalGateConfig(enabled=False, gates=gates)
        assert config.is_phase_gated("committing") is False

    def test_is_phase_gated_false_when_no_gate(self):
        """Test is_phase_gated returns False for non-gated phase."""
        gates = [GateConfig(phase="committing")]
        config = ApprovalGateConfig(enabled=True, gates=gates)
        assert config.is_phase_gated("planning") is False

    def test_add_gate(self):
        """Test adding a gate."""
        config = ApprovalGateConfig()
        config.add_gate(GateConfig(phase="committing"))
        assert len(config.gates) == 1
        assert config.gates[0].phase == "committing"

    def test_add_gate_duplicate_updates(self):
        """Test adding duplicate gate updates existing."""
        config = ApprovalGateConfig()
        config.add_gate(GateConfig(phase="committing", timeout_minutes=30))
        config.add_gate(GateConfig(phase="committing", timeout_minutes=60))
        assert len(config.gates) == 1
        assert config.gates[0].timeout_minutes == 60

    def test_remove_gate(self):
        """Test removing a gate."""
        gates = [GateConfig(phase="committing"), GateConfig(phase="implementing")]
        config = ApprovalGateConfig(gates=gates)
        config.remove_gate("committing")
        assert len(config.gates) == 1
        assert config.gates[0].phase == "implementing"

    def test_remove_gate_nonexistent(self):
        """Test removing a non-existent gate."""
        gates = [GateConfig(phase="committing")]
        config = ApprovalGateConfig(gates=gates)
        config.remove_gate("planning")  # Should not raise
        assert len(config.gates) == 1


class TestApprovalRequest:
    """Tests for ApprovalRequest model."""

    def test_approval_request_creation(self):
        """Test creating an approval request."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()
        timeout_at = requested_at + timedelta(minutes=30)

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            feature="Add login page",
            requested_at=requested_at,
            timeout_at=timeout_at,
        )

        assert request.id == "req-123"
        assert request.project_path == project_path
        assert request.phase == "committing"
        assert request.feature == "Add login page"
        assert request.requested_at == requested_at
        assert request.timeout_at == timeout_at
        assert request.decision == ApprovalDecision.PENDING
        assert request.comment is None
        assert request.resolved_at is None

    def test_approval_request_defaults(self):
        """Test ApprovalRequest with default values."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-456",
            project_path=project_path,
            phase="planning",
            requested_at=requested_at,
        )

        assert request.feature is None
        assert request.decision == ApprovalDecision.PENDING
        assert request.comment is None
        assert request.resolved_at is None

    def test_approve(self):
        """Test approving a request."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-789",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )

        request.approve("Looks good!")

        assert request.decision == ApprovalDecision.APPROVED
        assert request.comment == "Looks good!"
        assert request.resolved_at is not None
        assert isinstance(request.resolved_at, datetime)

    def test_approve_without_comment(self):
        """Test approving without a comment."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-abc",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )

        request.approve()

        assert request.decision == ApprovalDecision.APPROVED
        assert request.comment is None
        assert request.resolved_at is not None

    def test_reject(self):
        """Test rejecting a request."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-def",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )

        request.reject("Need more tests")

        assert request.decision == ApprovalDecision.REJECTED
        assert request.comment == "Need more tests"
        assert request.resolved_at is not None

    def test_timeout(self):
        """Test marking a request as timed out."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-ghi",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )

        request.timeout()

        assert request.decision == ApprovalDecision.TIMEOUT
        assert request.comment is None
        assert request.resolved_at is not None

    def test_is_pending_true(self):
        """Test is_pending returns True for pending request."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )

        assert request.is_pending() is True

    def test_is_pending_false_after_approval(self):
        """Test is_pending returns False after approval."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )
        request.approve()

        assert request.is_pending() is False

    def test_has_timed_out_true(self):
        """Test has_timed_out returns True when past timeout."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now() - timedelta(minutes=31)
        timeout_at = requested_at + timedelta(minutes=30)

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
            timeout_at=timeout_at,
        )

        assert request.has_timed_out() is True

    def test_has_timed_out_false(self):
        """Test has_timed_out returns False before timeout."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()
        timeout_at = requested_at + timedelta(minutes=30)

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
            timeout_at=timeout_at,
        )

        assert request.has_timed_out() is False

    def test_has_timed_out_no_timeout(self):
        """Test has_timed_out returns False when no timeout set."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )

        assert request.has_timed_out() is False

    def test_seconds_until_timeout_with_timeout(self):
        """Test seconds_until_timeout calculation."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()
        timeout_at = requested_at + timedelta(minutes=30)

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
            timeout_at=timeout_at,
        )

        seconds = request.seconds_until_timeout()
        assert seconds is not None
        assert 1790 <= seconds <= 1800  # Allow 10 second variance

    def test_seconds_until_timeout_no_timeout(self):
        """Test seconds_until_timeout returns None when no timeout."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )

        assert request.seconds_until_timeout() is None

    def test_seconds_until_timeout_after_timeout(self):
        """Test seconds_until_timeout returns negative after timeout."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now() - timedelta(minutes=31)
        timeout_at = requested_at + timedelta(minutes=30)

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
            timeout_at=timeout_at,
        )

        seconds = request.seconds_until_timeout()
        assert seconds is not None
        assert seconds < 0


class TestApprovalRequestSerialization:
    """Tests for ApprovalRequest serialization."""

    def test_to_dict(self):
        """Test converting ApprovalRequest to dict."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime(2025, 1, 15, 10, 30, 0)

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            feature="Add login page",
            requested_at=requested_at,
        )

        data = request.to_dict()

        assert data["id"] == "req-123"
        assert data["project_path"] == str(project_path)
        assert data["phase"] == "committing"
        assert data["feature"] == "Add login page"
        assert data["decision"] == "pending"

    def test_to_dict_with_resolution(self):
        """Test converting resolved ApprovalRequest to dict."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime(2025, 1, 15, 10, 30, 0)

        request = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            requested_at=requested_at,
        )
        request.approve("LGTM")

        data = request.to_dict()

        assert data["decision"] == "approved"
        assert data["comment"] == "LGTM"
        assert "resolved_at" in data

    def test_from_dict(self):
        """Test creating ApprovalRequest from dict."""
        data = {
            "id": "req-123",
            "project_path": "/tmp/test-project",
            "phase": "committing",
            "feature": "Add login page",
            "requested_at": "2025-01-15T10:30:00",
            "timeout_at": None,
            "decision": "pending",
            "comment": None,
            "resolved_at": None,
        }

        request = ApprovalRequest.from_dict(data)

        assert request.id == "req-123"
        assert request.project_path == Path("/tmp/test-project")
        assert request.phase == "committing"
        assert request.feature == "Add login page"
        assert request.decision == ApprovalDecision.PENDING

    def test_from_dict_with_path_object(self):
        """Test creating ApprovalRequest from dict with Path object."""
        data = {
            "id": "req-123",
            "project_path": Path("/tmp/test-project"),
            "phase": "committing",
            "requested_at": "2025-01-15T10:30:00",
            "decision": "pending",
        }

        request = ApprovalRequest.from_dict(data)

        assert request.project_path == Path("/tmp/test-project")

    def test_from_dict_with_decision(self):
        """Test creating ApprovalRequest from dict with decision."""
        data = {
            "id": "req-123",
            "project_path": "/tmp/test-project",
            "phase": "committing",
            "requested_at": "2025-01-15T10:30:00",
            "decision": "approved",
            "comment": "Looks good",
            "resolved_at": "2025-01-15T10:35:00",
        }

        request = ApprovalRequest.from_dict(data)

        assert request.decision == ApprovalDecision.APPROVED
        assert request.comment == "Looks good"
        assert request.resolved_at is not None

    def test_round_trip_serialization(self):
        """Test that serialization round-trip preserves data."""
        project_path = Path("/tmp/test-project")
        requested_at = datetime.now()

        original = ApprovalRequest(
            id="req-123",
            project_path=project_path,
            phase="committing",
            feature="Add login page",
            requested_at=requested_at,
        )
        original.approve("Approved after review")

        data = original.to_dict()
        restored = ApprovalRequest.from_dict(data)

        assert restored.id == original.id
        assert restored.project_path == original.project_path
        assert restored.phase == original.phase
        assert restored.feature == original.feature
        assert restored.decision == original.decision
        assert restored.comment == original.comment
