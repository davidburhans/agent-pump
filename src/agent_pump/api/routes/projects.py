"""Projects API endpoints."""

from fastapi import APIRouter, Request

from agent_pump.api.schemas import ProjectStatusDTO

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectStatusDTO])
async def list_projects(request: Request) -> list[ProjectStatusDTO]:
    """List all projects in the workspace."""
    project_service = request.app.state.project_service
    projects = project_service.list_projects()

    return [ProjectStatusDTO.from_internal(p) for p in projects]
