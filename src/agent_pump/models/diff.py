from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DiffChangeType(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"


class DiffHunk(BaseModel):
    """A contiguous block of changes in a diff."""

    model_config = ConfigDict(strict=True, frozen=True)

    header: str = Field(description="Hunk header (e.g., @@ -1,3 +1,4 @@)")
    lines: list[str] = Field(description="Lines in the hunk with +/- prefixes")


class DiffFile(BaseModel):
    """Represents a file with changes."""

    model_config = ConfigDict(strict=True, frozen=True)

    path: str = Field(description="File path relative to project root")
    status: DiffChangeType = Field(description="Type of change")
    hunks: list[DiffHunk] = Field(default_factory=list, description="List of change hunks")
    old_path: str | None = Field(default=None, description="Original path if renamed")
