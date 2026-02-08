"""Models for the interactive review dashboard."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    """Status of a review issue."""

    PENDING = "pending"
    FIXED = "fixed"
    IGNORED = "ignored"
    AUTO_FIX = "auto_fix"


class ReviewAction(BaseModel):
    """Action taken on a review issue."""

    issue_id: str  # Unique identifier for the issue (e.g. file:line:code)
    status: ReviewStatus
    resolution_details: str | None = None  # E.g. reason for ignoring, or fix applied
    auto_fix_prompt: str | None = None  # Custom prompt for auto-fix if needed


class IssueModel(BaseModel):
    """Pydantic model for an issue found during review."""

    file_path: str
    line_number: int | None
    severity: Literal["critical", "high", "medium", "low"]
    message: str
    suggestion: str = ""
    code: str | None = None  # Error code if available (e.g. E501)

    @property
    def id(self) -> str:
        """Generate a unique ID for the issue."""
        return f"{self.file_path}:{self.line_number or 0}:{self.message}"


class BestPracticeViolationModel(BaseModel):
    """Pydantic model for a best practice violation."""

    section: str
    requirement: str
    file_path: str
    line_number: int | None
    description: str

    @property
    def id(self) -> str:
        """Generate a unique ID for the violation."""
        return f"BP:{self.section}:{self.requirement}:{self.file_path}"


class ReviewReportModel(BaseModel):
    """Pydantic model for the full review report."""

    approved: bool
    issues: list[IssueModel] = Field(default_factory=list)
    violations: list[BestPracticeViolationModel] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    blocked: bool = False
