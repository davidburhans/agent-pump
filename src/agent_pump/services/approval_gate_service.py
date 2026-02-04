"""Approval gate service for managing approval requests.

This service handles approval gate logic including:
- Creating and tracking approval requests
- Timeout handling with configurable actions
- Batch approval operations
- Persistence of pending approvals
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agent_pump.events.bus import EventBus
from agent_pump.events.models import (
    ApprovalRequestedEvent,
    ApprovalResolvedEvent,
    ApprovalTimeoutEvent,
)
from agent_pump.models.approval_gate_config import (
    ApprovalDecision,
    ApprovalGateConfig,
    ApprovalRequest,
)

logger = logging.getLogger(__name__)


class ApprovalGateService:
    """Service for managing approval gates and requests.

    This service tracks pending approval requests, handles timeouts,
    and coordinates between the workflow and UI for approval decisions.
    """

    def __init__(self, event_bus: EventBus):
        """Initialize the approval gate service.

        Args:
            event_bus: Event bus for publishing approval events
        """
        self.event_bus = event_bus
        self._pending_approvals: dict[Path, dict[str, ApprovalRequest]] = {}
        self._timeout_task: asyncio.Task | None = None
        self._shutdown = False
        self._resolution_events: dict[str, asyncio.Event] = {}

    async def request_approval(
        self,
        project_path: Path,
        phase: str,
        config: ApprovalGateConfig,
        feature: str | None = None,
    ) -> ApprovalRequest | None:
        """Request approval for a workflow phase transition.

        Args:
            project_path: Path to the project
            phase: Workflow phase requiring approval
            feature: Current feature being worked on (optional)
            config: Approval gate configuration

        Returns:
            ApprovalRequest if approval is required, None otherwise
        """
        # Check if gates are enabled and this phase is gated
        if not config.is_phase_gated(phase):
            return None

        gate = config.get_gate_for_phase(phase)
        if not gate:
            return None

        # Check if there's already a pending request for this project/phase
        if project_path in self._pending_approvals:
            if phase in self._pending_approvals[project_path]:
                existing = self._pending_approvals[project_path][phase]
                if existing.is_pending():
                    logger.debug(f"Returning existing pending approval request {existing.id}")
                    return existing

        # Create new approval request
        requested_at = datetime.now()
        timeout_at = None
        if gate.timeout_minutes > 0:
            timeout_at = requested_at + timedelta(minutes=gate.timeout_minutes)

        request = ApprovalRequest(
            id=str(uuid.uuid4()),
            project_path=project_path,
            phase=phase,
            feature=feature,
            requested_at=requested_at,
            timeout_at=timeout_at,
        )

        # Store the request
        if project_path not in self._pending_approvals:
            self._pending_approvals[project_path] = {}
        self._pending_approvals[project_path][phase] = request

        # Create resolution event
        self._resolution_events[request.id] = asyncio.Event()

        # Start timeout monitor if needed
        if timeout_at and not self._timeout_task:
            self._timeout_task = asyncio.create_task(self._timeout_monitor())

        # Publish event
        await self.event_bus.publish(
            ApprovalRequestedEvent(
                project_path=project_path,
                phase=phase,
                feature=feature,
                request_id=request.id,
                requested_at=requested_at,
                timeout_at=timeout_at,
            )
        )

        logger.info(
            f"Approval requested for {project_path.name} phase {phase} (request: {request.id})"
        )

        return request

    async def resolve_approval(
        self,
        request_id: str,
        decision: ApprovalDecision,
        comment: str | None = None,
    ) -> bool:
        """Resolve an approval request with a decision.

        Args:
            request_id: ID of the approval request
            decision: The decision (approved, rejected, timeout)
            comment: Optional comment from approver

        Returns:
            True if resolved successfully, False if request not found or already resolved
        """
        # Find the request
        request = self.get_approval_by_id(request_id)
        if not request:
            logger.warning(f"Approval request {request_id} not found")
            return False

        # Check if already resolved
        if not request.is_pending():
            logger.warning(f"Approval request {request_id} is already resolved")
            return False

        # Apply the decision
        if decision == ApprovalDecision.APPROVED:
            request.approve(comment)
        elif decision == ApprovalDecision.REJECTED:
            request.reject(comment)
        elif decision == ApprovalDecision.TIMEOUT:
            request.timeout()
        else:
            logger.error(f"Invalid decision: {decision}")
            return False

        # Remove from pending
        if request.project_path in self._pending_approvals:
            phases = self._pending_approvals[request.project_path]
            if request.phase in phases and phases[request.phase].id == request_id:
                del phases[request.phase]
                if not phases:
                    del self._pending_approvals[request.project_path]

        # Signal resolution
        if request_id in self._resolution_events:
            self._resolution_events[request_id].set()

        # Publish event
        await self.event_bus.publish(
            ApprovalResolvedEvent(
                project_path=request.project_path,
                phase=request.phase,
                request_id=request_id,
                decision=decision.value,
                comment=comment,
                resolved_at=datetime.now(),
            )
        )

        logger.info(f"Approval request {request_id} resolved with {decision.value}")

        return True

    async def wait_for_approval(
        self,
        request_id: str,
        timeout: float | None = None,
    ) -> bool | None:
        """Wait for an approval request to be resolved.

        Args:
            request_id: ID of the approval request to wait for
            timeout: Maximum seconds to wait (None = forever)

        Returns:
            True if approved, False if rejected, None if timeout or error
        """
        request = self.get_approval_by_id(request_id)
        if not request:
            return None

        # Check if already resolved
        if not request.is_pending():
            if request.decision == ApprovalDecision.APPROVED:
                return True
            elif request.decision == ApprovalDecision.REJECTED:
                return False
            else:
                return None

        # Wait for resolution
        event = self._resolution_events.get(request_id)
        if not event:
            return None

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)

            # Check final decision
            request = self.get_approval_by_id(request_id)
            if not request:
                return None

            if request.decision == ApprovalDecision.APPROVED:
                return True
            elif request.decision == ApprovalDecision.REJECTED:
                return False
            else:
                return None

        except TimeoutError:
            logger.warning(f"Timeout waiting for approval {request_id}")
            return None

    def get_approval_by_id(self, request_id: str) -> ApprovalRequest | None:
        """Get an approval request by ID.

        Args:
            request_id: The request ID to look up

        Returns:
            The approval request if found, None otherwise
        """
        for phases in self._pending_approvals.values():
            for request in phases.values():
                if request.id == request_id:
                    return request
        return None

    def get_pending_approvals(
        self,
        project_path: Path | None = None,
        phase: str | None = None,
    ) -> list[ApprovalRequest]:
        """Get list of pending approval requests.

        Args:
            project_path: Filter by project (optional)
            phase: Filter by phase (optional)

        Returns:
            List of pending approval requests
        """
        results: list[ApprovalRequest] = []

        for path, phases in self._pending_approvals.items():
            if project_path and path != project_path:
                continue

            for request in phases.values():
                if phase and request.phase != phase:
                    continue
                if request.is_pending():
                    results.append(request)

        return results

    async def batch_approve_all(
        self,
        project_path: Path | None = None,
        phase: str | None = None,
        comment: str | None = None,
    ) -> int:
        """Approve all pending approval requests.

        Args:
            project_path: Only approve for this project (optional)
            phase: Only approve for this phase (optional)
            comment: Optional comment for all approvals

        Returns:
            Number of approvals granted
        """
        pending = self.get_pending_approvals(project_path, phase)
        count = 0

        for request in pending:
            if await self.resolve_approval(request.id, ApprovalDecision.APPROVED, comment):
                count += 1

        logger.info(f"Batch approved {count} approval requests")
        return count

    async def batch_reject_all(
        self,
        project_path: Path | None = None,
        phase: str | None = None,
        comment: str | None = None,
    ) -> int:
        """Reject all pending approval requests.

        Args:
            project_path: Only reject for this project (optional)
            phase: Only reject for this phase (optional)
            comment: Optional comment for all rejections

        Returns:
            Number of rejections made
        """
        pending = self.get_pending_approvals(project_path, phase)
        count = 0

        for request in pending:
            if await self.resolve_approval(request.id, ApprovalDecision.REJECTED, comment):
                count += 1

        logger.info(f"Batch rejected {count} approval requests")
        return count

    async def _timeout_monitor(self) -> None:
        """Background task to monitor and process timed-out approvals."""
        logger.debug("Starting approval timeout monitor")

        while not self._shutdown:
            try:
                await self._process_timeouts()

                # Sleep for a short interval before checking again
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                logger.debug("Timeout monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Error in timeout monitor: {e}")
                await asyncio.sleep(10)

        logger.debug("Approval timeout monitor stopped")

    async def _process_timeouts(self) -> None:
        """Process any approval requests that have timed out."""
        now = datetime.now()

        for path, phases in list(self._pending_approvals.items()):
            for phase, request in list(phases.items()):
                if not request.is_pending():
                    continue

                if request.timeout_at and now > request.timeout_at:
                    logger.info(
                        f"Approval request {request.id} timed out for {path.name} phase {phase}"
                    )

                    # Get the gate config to determine timeout action
                    # For now, we'll just timeout the request
                    # The workflow will handle the timeout action based on config
                    await self.resolve_approval(
                        request.id,
                        ApprovalDecision.TIMEOUT,
                        comment="Request timed out",
                    )

                    # Publish timeout event
                    await self.event_bus.publish(
                        ApprovalTimeoutEvent(
                            project_path=path,
                            phase=phase,
                            request_id=request.id,
                            timeout_action="timeout",
                            timeout_at=request.timeout_at,
                        )
                    )

    def get_approval_status_summary(self) -> dict[str, Any]:
        """Get a summary of current approval status.

        Returns:
            Dictionary with approval statistics
        """
        pending = self.get_pending_approvals()

        by_project: dict[str, int] = {}
        by_phase: dict[str, int] = {}

        for request in pending:
            project_key = str(request.project_path)
            by_project[project_key] = by_project.get(project_key, 0) + 1
            by_phase[request.phase] = by_phase.get(request.phase, 0) + 1

        return {
            "total_pending": len(pending),
            "by_project": by_project,
            "by_phase": by_phase,
        }

    def get_project_approval_status(self, project_path: Path) -> dict[str, Any]:
        """Get approval status for a specific project.

        Args:
            project_path: Path to the project

        Returns:
            Dictionary with project approval status
        """
        pending = self.get_pending_approvals(project_path=project_path)

        phases = {}
        for request in pending:
            phases[request.phase] = {
                "request_id": request.id,
                "feature": request.feature,
                "requested_at": request.requested_at.isoformat(),
                "timeout_at": request.timeout_at.isoformat() if request.timeout_at else None,
                "seconds_remaining": request.seconds_until_timeout(),
            }

        return {
            "has_pending": len(pending) > 0,
            "pending_count": len(pending),
            "phases": phases,
        }

    async def save_pending_approvals(self, state_file: Path) -> None:
        """Save pending approvals to a file for persistence.

        Args:
            state_file: Path to save the state file
        """
        pending = self.get_pending_approvals()
        data = {
            "saved_at": datetime.now().isoformat(),
            "approvals": [req.to_dict() for req in pending],
        }

        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(data, indent=2))

        logger.debug(f"Saved {len(pending)} pending approvals to {state_file}")

    async def load_pending_approvals(self, state_file: Path) -> None:
        """Load pending approvals from a file.

        Args:
            state_file: Path to the state file
        """
        if not state_file.exists():
            logger.debug(f"No pending approvals file found at {state_file}")
            return

        try:
            data = json.loads(state_file.read_text())

            for req_data in data.get("approvals", []):
                try:
                    request = ApprovalRequest.from_dict(req_data)

                    # Only restore if still pending
                    if request.is_pending():
                        if request.project_path not in self._pending_approvals:
                            self._pending_approvals[request.project_path] = {}
                        self._pending_approvals[request.project_path][request.phase] = request
                        self._resolution_events[request.id] = asyncio.Event()

                        # Check if already timed out
                        if request.has_timed_out():
                            logger.warning(f"Restored approval {request.id} already timed out")

                except Exception as e:
                    logger.error(f"Failed to restore approval request: {e}")

            count = len(self.get_pending_approvals())
            logger.info(f"Restored {count} pending approvals from {state_file}")

            # Start timeout monitor if we have pending approvals with timeouts
            has_timeouts = any(req.timeout_at is not None for req in self.get_pending_approvals())
            if has_timeouts and not self._timeout_task:
                self._timeout_task = asyncio.create_task(self._timeout_monitor())

        except Exception as e:
            logger.error(f"Failed to load pending approvals: {e}")

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        logger.info("Shutting down approval gate service")

        self._shutdown = True

        # Cancel timeout monitor
        if self._timeout_task:
            self._timeout_task.cancel()
            try:
                await self._timeout_task
            except asyncio.CancelledError:
                pass
            self._timeout_task = None

        # Clear resolution events
        self._resolution_events.clear()

        logger.debug("Approval gate service shutdown complete")
