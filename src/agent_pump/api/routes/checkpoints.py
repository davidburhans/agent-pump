import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agent_pump.api.routes.projects import normalize_path
from agent_pump.models.checkpoint import Checkpoint
from agent_pump.services.checkpoint_service import CheckpointService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["checkpoints"])


class CreateCheckpointRequest(BaseModel):
    description: str = Field(..., description="Description of the checkpoint")


class RollbackResponse(BaseModel):
    success: bool
    message: str


@router.get("/{project_path:path}/checkpoints", response_model=list[dict])
async def list_checkpoints(request: Request, project_path: str):
    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    try:
        service = CheckpointService(request.app.state.event_bus, path)
        return service.list_checkpoint_commits()
    except Exception as e:
        logger.exception(f"Failed to list checkpoints for {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_path:path}/checkpoints", response_model=Checkpoint)
async def create_checkpoint(request: Request, project_path: str, body: CreateCheckpointRequest):
    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    try:
        service = CheckpointService(request.app.state.event_bus, path)
        return service.create_checkpoint(
            phase="manual", description=body.description, auto_created=False
        )
    except Exception as e:
        logger.exception(f"Failed to create checkpoint for {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{project_path:path}/checkpoints/{commit_hash}/rollback", response_model=RollbackResponse
)
async def rollback_checkpoint(request: Request, project_path: str, commit_hash: str):
    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    try:
        service = CheckpointService(request.app.state.event_bus, path)
        mock_checkpoint = Checkpoint(
            phase="rollback",
            git_commit_hash=commit_hash,
            description="Rollback target",
        )

        success = service.rollback_to_checkpoint(mock_checkpoint)
        return RollbackResponse(
            success=success, message=f"Successfully rolled back to {commit_hash[:7]}"
        )
    except Exception as e:
        logger.exception(f"Failed to rollback checkpoint for {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
