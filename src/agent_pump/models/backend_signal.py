from enum import Enum
from typing import Any

from pydantic import BaseModel


class SignalType(str, Enum):
    DECISION = "decision"  # Backend made a decision
    REQUEST_INPUT = "request_input"  # Needs human input
    PROGRESS = "progress"  # Progress update
    SKIP_PHASE = "skip_phase"  # Skip current phase
    RETRY_PHASE = "retry_phase"  # Retry current phase
    ADD_ROADMAP = "add_roadmap"  # Add item to roadmap
    REQUEST_FILES = "request_files"  # Request more context


class BackendSignal(BaseModel):
    type: SignalType
    project_id: str
    phase: str
    payload: dict[str, Any]


class DecisionPayload(BaseModel):
    decision: str
    confidence: float  # 0.0 - 1.0
    reasoning: str | None = None
    metadata: dict[str, Any] = {}


class RequestInputPayload(BaseModel):
    question: str
    options: list[str] | None = None  # None = free text
    default: str | None = None
    timeout_seconds: int = 300  # 5 min default


class ProgressPayload(BaseModel):
    percent: int  # 0-100
    message: str
    phase_detail: str | None = None
