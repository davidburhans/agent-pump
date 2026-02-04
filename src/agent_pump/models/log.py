from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LogEntry:
    """
    Optimized storage for log entries.
    Using slots=True saves ~15-20% memory for large lists.
    """

    timestamp: str
    message: str
    project_path: Path | None
    state: str
    task: str | None
    renderable: Any = None  # rich.console.RenderableType, kept as Any to avoid circular deps
