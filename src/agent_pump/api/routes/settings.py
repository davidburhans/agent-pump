"""Settings API endpoints for workspace configuration."""

from fastapi import APIRouter, Request

from agent_pump.api.schemas import ModelCatalogDTO, ModelCatalogUpdateRequest

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/model-catalog", response_model=ModelCatalogDTO)
async def get_model_catalog(request: Request) -> ModelCatalogDTO:
    """Get the current model catalog (available models per backend)."""
    workspace_service = request.app.state.workspace_service
    workspace = workspace_service.get_current_workspace()
    return ModelCatalogDTO.from_internal(workspace.model_catalog)


@router.put("/model-catalog", response_model=ModelCatalogDTO)
async def update_model_catalog(
    request: Request, update: ModelCatalogUpdateRequest
) -> ModelCatalogDTO:
    """Update the model catalog (available models per backend)."""
    workspace_service = request.app.state.workspace_service
    workspace = workspace_service.get_current_workspace()
    workspace.model_catalog.backends = update.backends
    workspace.save()
    return ModelCatalogDTO.from_internal(workspace.model_catalog)
