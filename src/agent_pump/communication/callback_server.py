from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from agent_pump.models.backend_signal import BackendSignal, SignalType

router = APIRouter(prefix="/callback", tags=["Backend Callbacks"])


@router.post("/signal")
async def receive_signal(signal: BackendSignal, request: Request):
    """
    Main endpoint for backend signals.
    Routes to appropriate handler based on signal.type.
    """
    handlers = {
        SignalType.REQUEST_INPUT: handle_request_input,
    }
    handler = handlers.get(signal.type)
    if not handler:
        # For now, just log/ignore other signals as they are not fully implemented
        return {"status": "ignored", "reason": f"Signal type {signal.type} not handled yet"}

    return await handler(signal, request)


async def handle_request_input(signal: BackendSignal, request: Request):
    """
    Pause workflow and wait for human input.
    """
    try:
        project_path = Path(signal.project_id).resolve()
    except Exception:
        raise HTTPException(400, f"Invalid project path: {signal.project_id}")

    project_service = getattr(request.app.state, "project_service", None)
    if not project_service:
        raise HTTPException(500, "Project service not initialized")

    # Check if project exists and has a workflow
    if project_path not in project_service.workflows:
        # Try to find by string match if direct path lookup fails (e.g. slight path diffs)
        found = False
        for p, w in project_service.workflows.items():
            if str(p) == signal.project_id:
                project_path = p
                found = True
                break

        if not found:
            raise HTTPException(404, f"Project workflow not found: {signal.project_id}")

    workflow = project_service.workflows[project_path]

    # Parse payload
    question = signal.payload.get("question")
    if not question:
        raise HTTPException(400, "Missing question in payload")

    options = signal.payload.get("options")
    timeout = signal.payload.get("timeout_seconds", 300)

    try:
        # This will block until the user responds in the TUI or timeout
        response = await workflow.request_input(question, options, timeout)
        return {"status": "ok", "response": response}
    except Exception as e:
        return {"status": "error", "message": str(e)}
