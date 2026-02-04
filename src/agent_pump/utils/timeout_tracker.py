"""Timeout instrumentation for tracking hanging operations."""

import logging
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TimeoutType(Enum):
    """Types of timeouts that can occur."""

    BACKEND_EXECUTION = "backend_execution"
    VERIFICATION_BUILD = "verification_build"
    VERIFICATION_LINT = "verification_lint"
    VERIFICATION_TEST = "verification_test"
    WORKFLOW_PHASE = "workflow_phase"


@dataclass
class TimeoutEvent:
    """Record of a timeout event."""

    timestamp: float
    timeout_type: TimeoutType
    operation_name: str
    timeout_seconds: int
    duration_before_timeout: float
    project_name: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


class TimeoutTracker:
    """Track timeout events to identify patterns."""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.history: list[TimeoutEvent] = []
        self._pending_operations: dict[str, dict[str, Any]] = {}

    def start_operation(
        self,
        operation_id: str,
        timeout_type: TimeoutType,
        operation_name: str,
        timeout_seconds: int,
        project_name: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Record the start of an operation that may timeout."""
        self._pending_operations[operation_id] = {
            "start_time": time.time(),
            "timeout_type": timeout_type,
            "operation_name": operation_name,
            "timeout_seconds": timeout_seconds,
            "project_name": project_name,
            "context": context or {},
        }
        logger.debug(f"Started tracked operation {operation_id}: {operation_name}")

    def record_timeout(self, operation_id: str) -> None:
        """Record a timeout for a pending operation."""
        if operation_id not in self._pending_operations:
            logger.warning(f"Timeout recorded for unknown operation: {operation_id}")
            return

        op = self._pending_operations.pop(operation_id)
        duration = time.time() - op["start_time"]

        event = TimeoutEvent(
            timestamp=time.time(),
            timeout_type=op["timeout_type"],
            operation_name=op["operation_name"],
            timeout_seconds=op["timeout_seconds"],
            duration_before_timeout=duration,
            project_name=op["project_name"],
            context=op["context"],
        )

        self.history.append(event)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        logger.warning(
            f"TIMEOUT: {event.operation_name} "
            f"(type={event.timeout_type.value}, "
            f"limit={event.timeout_seconds}s, "
            f"actual={event.duration_before_timeout:.1f}s, "
            f"project={event.project_name})"
        )

    def complete_operation(self, operation_id: str, success: bool = True) -> None:
        """Record completion of a tracked operation."""
        if operation_id in self._pending_operations:
            op = self._pending_operations.pop(operation_id)
            duration = time.time() - op["start_time"]

            if success:
                logger.debug(
                    f"Completed operation {operation_id}: {op['operation_name']} in {duration:.1f}s"
                )
            else:
                logger.warning(
                    f"Failed operation {operation_id}: {op['operation_name']} after {duration:.1f}s"
                )

    def get_timeout_patterns(self) -> dict[str, Any]:
        """Analyze timeout patterns from history."""
        if not self.history:
            return {"message": "No timeouts recorded"}

        by_type: dict[str, list[TimeoutEvent]] = {}
        for event in self.history:
            key = event.timeout_type.value
            if key not in by_type:
                by_type[key] = []
            by_type[key].append(event)

        patterns = {
            "total_timeouts": len(self.history),
            "by_type": {
                key: {
                    "count": len(events),
                    "most_common_project": self._most_common([e.project_name for e in events]),
                    "average_duration": sum(e.duration_before_timeout for e in events)
                    / len(events),
                }
                for key, events in by_type.items()
            },
        }

        return patterns

    def _most_common(self, items: list[str | None]) -> str | None:
        """Find most common non-None item."""
        non_none = [i for i in items if i is not None]
        if not non_none:
            return None
        return Counter(non_none).most_common(1)[0][0]


# Global instance
timeout_tracker = TimeoutTracker()
