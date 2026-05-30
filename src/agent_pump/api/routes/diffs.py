"""Diff API endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request

from agent_pump.api.routes.projects import normalize_path
from agent_pump.models.diff import DiffFile
from agent_pump.services.diff_service import DiffService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["diffs"])

@router.get("/{project_path:path}/diff", response_model=list[DiffFile])
async def get_project_diff(request: Request, project_path: str, diff_type: str = "all"):
    """Get git diff for a project."""
    try:
        path = normalize_path(project_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid project path: {e}")

    try:
        diff_service = DiffService(path)
        diff_files = diff_service.get_diffs_by_type(diff_type)
        return diff_files
    except Exception as e:
        logger.exception(f"Failed to get diff for {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get diff: {e}")
