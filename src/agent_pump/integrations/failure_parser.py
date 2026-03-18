"""Parser for CI failure logs."""

import re
from typing import Any

from pydantic import BaseModel, Field


class FailureInfo(BaseModel):
    """Information extracted from failure logs."""

    errors: list[dict[str, Any]] = Field(description="List of extracted errors")
    raw_log: str = Field(description="Relevant segment of the raw log")
    suggested_fix: str = Field(description="Suggested fix based on errors")
    run_id: int | None = Field(default=None, description="CI Run ID")


class FailureParser:
    """Parse CI logs to extract actionable failure info."""

    PATTERNS = [
        # Python
        (r"(\w+Error): (.+)", "python_error"),
        (r"FAILED (.+\.py)::(\w+)", "pytest_failure"),
        # JavaScript
        (r"error TS(\d+): (.+)", "typescript_error"),
        (r"✕ (.+)", "jest_failure"),
        # Rust
        (r"error\[E(\d+)\]: (.+)", "rust_error"),
        # Generic
        (r"(?i)\berror: (.+)", "generic_error"),
    ]

    def parse(self, logs: str) -> FailureInfo:
        """Parse logs and extract failure info."""
        errors = []
        # Keep last 5000 chars for context if log is huge
        raw_log = logs[-5000:] if len(logs) > 5000 else logs

        for pattern, error_type in self.PATTERNS:
            matches = re.findall(pattern, logs)
            for match in matches:
                # match can be a tuple or string
                details = match if isinstance(match, str) else ": ".join(match)
                # Deduplicate roughly
                error_entry = {"type": error_type, "details": details}
                if error_entry not in errors:
                    errors.append(error_entry)

        return FailureInfo(
            errors=errors,
            raw_log=raw_log,
            suggested_fix=self._suggest_fix(errors),
        )

    def _suggest_fix(self, errors: list[dict[str, Any]]) -> str:
        """Suggest a fix based on errors found."""
        if not errors:
            return "Investigate CI logs (no specific error pattern matched)"

        # Simple heuristics
        for error in errors:
            details = str(error["details"])
            if error["type"] == "python_error":
                if "ModuleNotFound" in details:
                    return "Install missing dependency"
                if "IndentationError" in details:
                    return "Fix indentation"
            if error["type"] == "typescript_error":
                return "Fix TypeScript type errors"
            if error["type"] == "pytest_failure":
                return "Fix failing unit tests"

        return "Review and fix failing tests/build"
