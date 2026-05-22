"""Settings API endpoints for workspace configuration."""

from fastapi import APIRouter, Request

from agent_pump.api.schemas import (
    BackendPresetDTO,
    GeneralSettingsDTO,
    ModelCatalogDTO,
    ModelCatalogUpdateRequest,
)
from agent_pump.models.workspace import BackendFallback, BackendInstance, BackendPreset

router = APIRouter(prefix="/settings", tags=["settings"])


def fallback_dto_to_internal(dto) -> BackendFallback:
    backends = [
        BackendInstance(
            name=b.name,
            args=b.args,
            timeout=b.timeout,
            concurrency_limit=b.concurrency_limit
        ) for b in dto.backends
    ]
    return BackendFallback(backends=backends)


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


@router.get("/general", response_model=GeneralSettingsDTO)
async def get_general_settings(request: Request) -> GeneralSettingsDTO:
    """Get general workspace settings."""
    workspace_service = request.app.state.workspace_service
    workspace = workspace_service.get_current_workspace()
    return GeneralSettingsDTO(notifications_enabled=workspace.notifications_enabled)


@router.put("/general", response_model=GeneralSettingsDTO)
async def update_general_settings(
    request: Request, settings: GeneralSettingsDTO
) -> GeneralSettingsDTO:
    """Update general workspace settings."""
    workspace_service = request.app.state.workspace_service
    workspace = workspace_service.get_current_workspace()
    workspace.notifications_enabled = settings.notifications_enabled
    workspace.save()
    return GeneralSettingsDTO(notifications_enabled=workspace.notifications_enabled)


@router.post("/test-notification")
async def test_notification() -> dict[str, str]:
    """Trigger a test notification."""
    from agent_pump.utils.notifier import Notifier
    try:
        Notifier.test()
        return {"status": "success", "message": "Test notification sent successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/presets", response_model=BackendPresetDTO)
async def save_backend_preset(
    request: Request, preset: BackendPresetDTO
) -> BackendPresetDTO:
    """Save a backend preset to the workspace."""
    workspace_service = request.app.state.workspace_service
    workspace = workspace_service.get_current_workspace()

    internal_fallback = fallback_dto_to_internal(preset.backends)
    internal_preset = BackendPreset(name=preset.name, backends=internal_fallback)

    workspace.backend_presets[preset.name] = internal_preset
    workspace.save()

    return BackendPresetDTO.from_internal(internal_preset)

