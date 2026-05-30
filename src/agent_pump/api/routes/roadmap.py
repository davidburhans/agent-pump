"""Roadmap API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agent_pump.api.routes.projects import normalize_path
from agent_pump.models.roadmap import Roadmap, RoadmapStatus
from agent_pump.services.roadmap_service import RoadmapService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["roadmap"])


class IdeaSubmit(BaseModel):
    """Request model for submitting a new idea."""
    title: str = Field(..., description="Idea title")
    description: str = Field("", description="Detailed description")
    priority: str = Field("Medium", description="Priority level")
    section: str = Field("future", description="Target section ('current', 'future', 'deferred')")
    position: str = Field("bottom", description="Position to insert ('top', 'bottom')")


@router.get("/{project_path:path}/roadmap", response_model=Roadmap)
async def get_roadmap(request: Request, project_path: str) -> Roadmap:
    """Get the roadmap for a specific project."""
    project_service = request.app.state.project_service

    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    project = project_service.get_project(path)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    roadmap_service = RoadmapService(project)
    try:
        return roadmap_service.load()
    except Exception as e:
        logger.exception(f"Failed to load roadmap for {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load roadmap: {e}")


@router.post("/{project_path:path}/roadmap/ideas")
async def submit_idea(request: Request, project_path: str, body: IdeaSubmit):
    """Submit a new idea to the roadmap."""
    project_service = request.app.state.project_service

    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    project = project_service.get_project(path)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    roadmap_service = RoadmapService(project)
    try:
        roadmap_service.add_item(
            title=body.title,
            description=body.description,
            priority=body.priority,
            status=RoadmapStatus.NOT_STARTED,
            section=body.section,
            position=body.position,
        )
        return {"success": True, "message": "Idea added to roadmap"}
    except Exception as e:
        logger.exception(f"Failed to add idea to roadmap for {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add idea: {e}")
