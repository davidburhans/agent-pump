"""Webhook routes for external triggers."""

import hashlib
import hmac
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from agent_pump.models.project import ProjectStatus
from agent_pump.models.webhook_config import WebhookConfig

logger = logging.getLogger(__name__)

router = APIRouter()


def validate_github_signature(body: bytes, signature: str, secret: str) -> bool:
    """Validate GitHub webhook signature."""
    if not signature:
        return False
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def validate_slack_signature(
    body: bytes, signature: str, timestamp: str, secret: str
) -> bool:
    """Validate Slack webhook signature."""
    if not signature or not timestamp:
        return False

    # Slack signature format: v0=HMAC_SHA256(secret, "v0:timestamp:body")
    basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"v0={expected}", signature)


async def start_workflow_task(project_path: Path, app_state: Any) -> None:
    """Background task to start a project workflow."""
    try:
        # Ensure project is loaded in service
        project_service = app_state.project_service
        # add_project returns the project object (loaded or existing)
        await project_service.add_project(project_path)

        # Get workflow
        workflow = project_service.workflows.get(project_path)
        if not workflow:
            logger.error(f"Workflow not found for {project_path}")
            return

        if workflow.is_running():
            logger.info(f"Workflow for {project_path} is already running. Skipping trigger.")
            return

        # Check status and reset if needed
        if workflow.project.status in (ProjectStatus.COMPLETED, ProjectStatus.ERROR):
             workflow.reset_workflow()

        # Run workflow
        logger.info(f"Starting workflow for {project_path} via webhook trigger")
        # Run in background task loop
        await workflow.run()

    except Exception as e:
        logger.exception(f"Failed to start workflow for {project_path}: {e}")


async def handle_github_webhook(
    request: Request, body: bytes, background_tasks: BackgroundTasks, config: WebhookConfig
) -> dict:
    """Handle GitHub webhook payload."""
    event_type = request.headers.get("X-GitHub-Event")

    if event_type == "ping":
        return {"status": "pong", "message": "GitHub webhook ping received"}

    if event_type != "push":
        return {"status": "ignored", "reason": f"Event {event_type} not supported"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Check branch
    ref = payload.get("ref", "")
    branch = ref.split("/")[-1]

    if branch not in config.auto_trigger_branches:
        return {"status": "ignored", "reason": f"Branch {branch} not in auto_trigger_branches"}

    repo_full_name = payload.get("repository", {}).get("full_name")
    if not repo_full_name:
         return {"status": "ignored", "reason": "No repository name found"}

    # Find project
    workspace = request.app.state.workspace_service.get_current_workspace()
    target_path = None

    # Check all projects in workspace config
    for path_str, proj_config in workspace.projects.items():
        if (
            proj_config.github_integration
            and proj_config.github_integration.owner
            and proj_config.github_integration.repo
        ):
            full_name = f"{proj_config.github_integration.owner}/{proj_config.github_integration.repo}"
            if full_name == repo_full_name:
                target_path = Path(path_str)
                break

    if target_path:
        background_tasks.add_task(start_workflow_task, target_path, request.app.state)
        return {"status": "triggered", "project": str(target_path)}

    return {"status": "ignored", "reason": f"No project found for {repo_full_name}"}


async def handle_slack_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> dict:
    """Handle Slack slash command."""
    # Command: /agent-pump [action] [project_name]
    # Slack sends form-encoded data
    form_data = await request.form()

    command = form_data.get("command")
    text = form_data.get("text", "").strip().split()

    if command == "/agent-pump":
        action = text[0] if text else "status"

        if action == "start":
            if len(text) < 2:
                 return {"text": "Please specify a project name. Usage: `/agent-pump start <project_name>`"}

            project_name = text[1]

            # Find project by name
            app_state = request.app.state
            workspace = app_state.workspace_service.get_current_workspace()
            target_path = None

            # 1. Exact match on config name
            for path_str, proj_config in workspace.projects.items():
                if proj_config.name == project_name:
                    target_path = Path(path_str)
                    break

            # 2. Fallback: match directory name
            if not target_path:
                 for path_str in workspace.projects:
                     p = Path(path_str)
                     if p.name == project_name:
                         target_path = p
                         break

            if target_path:
                background_tasks.add_task(start_workflow_task, target_path, app_state)
                return {"text": f"🚀 Triggered workflow for project '{project_name}'"}

            return {"text": f"Project '{project_name}' not found."}

        elif action == "status":
             return {"text": "Status: Online (Detailed status reporting not implemented via webhook yet)"}

    return {"text": f"Unknown command or action. Received: {command} {text}"}


@router.post("/trigger/{source}")
async def webhook_trigger(
    source: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_slack_signature: str | None = Header(None, alias="X-Slack-Signature"),
    x_slack_request_timestamp: str | None = Header(None, alias="X-Slack-Request-Timestamp"),
    x_signature: str | None = Header(None, alias="X-Signature"),
):
    """
    Handle incoming webhooks.

    Supported sources:
    - github: Triggers on push events to configured branches.
    - slack: Triggers via slash commands.
    - custom: Generic trigger.
    """
    app_state = request.app.state
    workspace = app_state.workspace_service.get_current_workspace()

    # Ensure webhook_config exists (it should with default factory)
    if not hasattr(workspace, "webhook_config"):
        # Fallback if model not updated in memory correctly (shouldn't happen if restarted)
        config = WebhookConfig()
    else:
        config = workspace.webhook_config

    if not config.enabled:
        raise HTTPException(status_code=503, detail="Webhooks disabled")

    if source not in config.allowed_sources:
        raise HTTPException(status_code=403, detail="Source not allowed")

    body = await request.body()

    # Signature Validation
    if config.secret_key:
        if source == "github":
            if not x_hub_signature_256 or not validate_github_signature(
                body, x_hub_signature_256, config.secret_key
            ):
                raise HTTPException(status_code=401, detail="Invalid GitHub signature")

        elif source == "slack":
            if not x_slack_signature or not x_slack_request_timestamp:
                raise HTTPException(status_code=401, detail="Missing Slack headers")

            if not validate_slack_signature(
                body, x_slack_signature, x_slack_request_timestamp, config.secret_key
            ):
                raise HTTPException(status_code=401, detail="Invalid Slack signature")

        # For custom/other sources, maybe define a standard header?
        # For now, skip generic validation if source specific logic applies.
        # If generic source, maybe use X-Signature with generic HMAC logic.
        elif x_signature:
             # Generic validation
             expected = hmac.new(config.secret_key.encode(), body, hashlib.sha256).hexdigest()
             if not hmac.compare_digest(f"sha256={expected}", x_signature) and \
                not hmac.compare_digest(expected, x_signature):
                 raise HTTPException(status_code=401, detail="Invalid signature")

    # Process Payload
    try:
        if source == "github":
            return await handle_github_webhook(request, body, background_tasks, config)
        elif source == "slack":
            return await handle_slack_webhook(request, background_tasks)
        else:
            return {"status": "received", "message": "Custom webhook received"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))
