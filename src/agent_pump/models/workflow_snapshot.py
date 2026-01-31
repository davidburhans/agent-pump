from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


NodeStatus = Literal["pending", "active", "completed", "error", "skipped"]


class NodeSnapshot(BaseModel):
    """Snapshot of a single node in the workflow graph."""
    
    id: str = Field(description="Unique identifier for the node (usually phase name)")
    label: str = Field(description="Display label")
    status: NodeStatus = Field(default="pending")
    icon: str = Field(default="●")
    is_active: bool = Field(default=False)
    
    model_config = ConfigDict(frozen=True)


class EdgeSnapshot(BaseModel):
    """Snapshot of an edge between nodes."""
    
    source: str
    target: str
    active: bool = Field(default=False)
    
    model_config = ConfigDict(frozen=True)


class WorkflowSnapshot(BaseModel):
    """Complete snapshot of the workflow state for visualization."""
    
    project_path: str
    project_name: str
    current_state: str
    nodes: list[NodeSnapshot]
    edges: list[EdgeSnapshot]
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(frozen=True)
