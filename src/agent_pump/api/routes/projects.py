"""Projects API endpoints."""

import logging
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agent_pump.api.schemas import ProjectStatusDTO, WorkflowStateDTO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


def normalize_path(project_path: str) -> Path:
    """Convert a WSL or Windows path to an absolute Path, normalized for consistent comparison."""
    # Handle double-encoded paths (e.g., %2F -> /)
    decoded = project_path.replace("%2F", "/")

    # Remove leading/trailing whitespace
    decoded = decoded.strip()

    # Remove leading slashes to normalize: ///mnt/c/... -> mnt/c/...
    decoded = decoded.lstrip("/")

    # Handle WSL paths: mnt/c/... -> C:/...
    wsl_match = re.match(r"^mnt/([a-z])[/\\](.*)$", decoded)
    if wsl_match:
        drive_letter = wsl_match.group(1).upper()
        rest = wsl_match.group(2)
        return Path(f"{drive_letter}:/{rest}").resolve()

    # Handle plain Windows paths (c:/... or C:/...)
    win_match = re.match(r"^([a-zA-Z]):?[/\\](.*)$", decoded)
    if win_match:
        drive_letter = win_match.group(1).upper()
        rest = win_match.group(2)
        return Path(f"{drive_letter}:/{rest}").resolve()

    # Fallback - try resolving as-is
    return Path(decoded).resolve()


@router.get("", response_model=list[ProjectStatusDTO])
async def list_projects(request: Request) -> list[ProjectStatusDTO]:
    """List all projects in the workspace."""
    project_service = request.app.state.project_service
    projects = project_service.list_projects()

    return [ProjectStatusDTO.from_internal(p) for p in projects]


@router.get("/{project_path:path}/workflow", response_model=WorkflowStateDTO)
async def get_project_workflow(request: Request, project_path: str) -> WorkflowStateDTO:
    """Get the workflow state for a specific project."""
    project_service = request.app.state.project_service

    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    # Normalize path for consistent string comparison
    path_str = str(path.resolve()).lower()
    logger.info(f"Looking up workflow for path: {path} (normalized: {path_str})")
    logger.info(
        f"Available workflow keys: {[str(k).lower() for k in project_service.workflows.keys()]}"
    )

    # Find matching workflow by normalized string comparison
    workflow = None
    for key in project_service.workflows.keys():
        if str(key.resolve()).lower() == path_str:
            workflow = project_service.workflows[key]
            break

    if not workflow:
        logger.warning(f"Workflow not found for {path} (tried {path_str})")
        raise HTTPException(status_code=404, detail="Project workflow not found")

    return WorkflowStateDTO.from_internal(workflow)


class AddProjectRequest(BaseModel):
    """Request model for adding a new project."""

    path: str = Field(description="Absolute path to the project root directory")


class ProjectControlResponse(BaseModel):
    """Response model for project control actions."""

    success: bool = Field(description="Whether the action succeeded")
    message: str = Field(description="Detail message of the action outcome")


@router.post("/{project_path:path}/start", response_model=ProjectControlResponse)
async def start_project(request: Request, project_path: str) -> ProjectControlResponse:
    """Start executing the project workflow."""
    project_service = request.app.state.project_service
    workflow_service = request.app.state.workflow_service

    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    path_str = str(path.resolve()).lower()
    resolved_path = None
    for key in project_service.workflows.keys():
        if str(key.resolve()).lower() == path_str:
            resolved_path = key
            break

    if not resolved_path:
        raise HTTPException(status_code=404, detail="Project workflow not found")

    success = await workflow_service.start_project(resolved_path)
    if not success:
        return ProjectControlResponse(
            success=False,
            message="Workflow failed to start. It may already be running, or queue is full."
        )

    return ProjectControlResponse(success=True, message="Workflow started successfully.")


@router.post("/{project_path:path}/stop", response_model=ProjectControlResponse)
async def stop_project(request: Request, project_path: str) -> ProjectControlResponse:
    """Halt execution of the active workflow."""
    project_service = request.app.state.project_service
    workflow_service = request.app.state.workflow_service

    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    path_str = str(path.resolve()).lower()
    resolved_path = None
    for key in project_service.workflows.keys():
        if str(key.resolve()).lower() == path_str:
            resolved_path = key
            break

    if not resolved_path:
        raise HTTPException(status_code=404, detail="Project workflow not found")

    success = await workflow_service.stop_project(resolved_path)
    if not success:
        return ProjectControlResponse(
            success=False,
            message="Workflow failed to stop."
        )

    return ProjectControlResponse(success=True, message="Workflow stopped successfully.")


@router.post("/{project_path:path}/reset", response_model=ProjectControlResponse)
async def reset_project(request: Request, project_path: str) -> ProjectControlResponse:
    """Reset iteration count and return project to the idle state."""
    project_service = request.app.state.project_service
    workflow_service = request.app.state.workflow_service

    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    path_str = str(path.resolve()).lower()
    resolved_path = None
    for key in project_service.workflows.keys():
        if str(key.resolve()).lower() == path_str:
            resolved_path = key
            break

    if not resolved_path:
        raise HTTPException(status_code=404, detail="Project workflow not found")

    success = await workflow_service.reset_project(resolved_path)
    if not success:
        return ProjectControlResponse(
            success=False,
            message="Workflow failed to reset."
        )

    return ProjectControlResponse(success=True, message="Workflow reset successfully.")


@router.post("/{project_path:path}/skip", response_model=ProjectControlResponse)
async def skip_project_feature(request: Request, project_path: str) -> ProjectControlResponse:
    """Skip the current feature in progress and advance the roadmap."""
    project_service = request.app.state.project_service

    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    path_str = str(path.resolve()).lower()
    workflow = None
    for key in project_service.workflows.keys():
        if str(key.resolve()).lower() == path_str:
            workflow = project_service.workflows[key]
            break

    if not workflow:
        raise HTTPException(status_code=404, detail="Project workflow not found")

    if not workflow.project.current_feature:
        raise HTTPException(status_code=400, detail="No feature in progress to skip")

    failed_feature = workflow.project.current_feature
    workflow.project.failed_features.append(failed_feature)
    workflow.project.current_feature = None

    # Sync state change to persisted state
    workflow.workflow_state.current_feature = None
    workflow.workflow_state.failed_features = workflow.project.failed_features
    workflow.workflow_state.save()

    # Cancel if running
    if workflow.is_running():
        workflow.cancel()

    # Trigger UI refresh by notifying state change (even if state is same)
    if workflow.on_state_change:
        workflow.on_state_change(
            workflow.workflow_state.current_state, workflow.workflow_state.current_state
        )

    return ProjectControlResponse(
        success=True,
        message=f"Feature '{failed_feature}' skipped successfully."
    )


@router.post("/add", response_model=ProjectStatusDTO)
async def add_project(request: Request, body: AddProjectRequest) -> ProjectStatusDTO:
    """Add a new project workspace."""
    project_service = request.app.state.project_service
    try:
        path = normalize_path(body.path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    if not path.exists() or not path.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path '{path}' does not exist or is not a directory."
        )

    try:
        project = await project_service.add_project(path)
    except Exception as e:
        logger.exception(f"Failed to add project at {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add project: {e}")

    return ProjectStatusDTO.from_internal(project)


@router.delete("/{project_path:path}", response_model=ProjectControlResponse)
async def remove_project(request: Request, project_path: str) -> ProjectControlResponse:
    """Remove a project from the workspace list."""
    project_service = request.app.state.project_service
    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    success = await project_service.remove_project(path)
    if not success:
        return ProjectControlResponse(
            success=False,
            message="Failed to remove project from workspace. It might not be registered."
        )

    return ProjectControlResponse(
        success=True,
        message=f"Project at '{path}' was successfully removed from workspace."
    )
