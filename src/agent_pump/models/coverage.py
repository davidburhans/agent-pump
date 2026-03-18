"""Coverage data models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CoverageReportModel(BaseModel):
    """Model representing a code coverage report."""

    total_coverage: float = Field(..., description="Total coverage percentage (0.0 to 100.0)")
    files: dict[str, float] = Field(
        default_factory=dict,
        description="Dictionary mapping file paths to their coverage percentage",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When this report was generated"
    )
    raw_output: str | None = Field(default=None, description="Raw output from the coverage tool")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary suitable for JSON serialization."""
        return self.model_dump(mode="json")
