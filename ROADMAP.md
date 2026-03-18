# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [docs/features.md](docs/features.md).

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

### 🔴 Interactive Review Dashboard
**Priority: High**

Allow users to interactively review and resolve issues found during the automated review phase:
- **TUI Modal**: dedicated screen for reviewing code quality issues and best practice violations.
- **Interactive Resolution**: Mark issues as "Fixed", "Ignored" (with reason), or "Auto-fix".
- **AI Auto-fix**: Button to trigger AI backend to generate fix for specific issue.
- **Review Decision**: Manually approve or reject the review to unblock merge.
- **Diff View Integration**: Jump to diff viewer for specific file/line of issue.

---

### 🔴 Backend Communication Protocol
**Priority: High**

Enable rich bidirectional communication between backends and Agent Pump for complex workflow decisions beyond simple pass/fail.

#### Implementation Overview

```
src/agent_pump/
├── communication/
│   ├── __init__.py
│   ├── callback_server.py      # HTTP callback endpoints
│   ├── mcp_server.py           # MCP server implementation
│   ├── protocol.py             # Shared message types
│   └── injection.py            # Inject config into backend env
├── models/
│   └── backend_signal.py       # Pydantic models for signals
```

#### Step 1: Define Signal Models (`src/agent_pump/models/backend_signal.py`)

```python
from pydantic import BaseModel
from enum import Enum
from typing import Any

class SignalType(str, Enum):
    DECISION = "decision"           # Backend made a decision
    REQUEST_INPUT = "request_input" # Needs human input
    PROGRESS = "progress"           # Progress update
    SKIP_PHASE = "skip_phase"       # Skip current phase
    RETRY_PHASE = "retry_phase"     # Retry current phase
    ADD_ROADMAP = "add_roadmap"     # Add item to roadmap
    REQUEST_FILES = "request_files" # Request more context

class BackendSignal(BaseModel):
    type: SignalType
    project_id: str
    phase: str
    payload: dict[str, Any]
    
class DecisionPayload(BaseModel):
    decision: str
    confidence: float  # 0.0 - 1.0
    reasoning: str | None = None
    metadata: dict[str, Any] = {}

class RequestInputPayload(BaseModel):
    question: str
    options: list[str] | None = None  # None = free text
    default: str | None = None
    timeout_seconds: int = 300  # 5 min default

class ProgressPayload(BaseModel):
    percent: int  # 0-100
    message: str
    phase_detail: str | None = None
```

#### Step 2: HTTP Callback Server (`src/agent_pump/communication/callback_server.py`)

Extend the existing FastAPI server in `src/agent_pump/api/server.py`:

```python
from fastapi import APIRouter, HTTPException
from agent_pump.models.backend_signal import BackendSignal, SignalType

router = APIRouter(prefix="/api/callback", tags=["Backend Callbacks"])

@router.post("/signal")
async def receive_signal(signal: BackendSignal):
    """
    Main endpoint for backend signals.
    Routes to appropriate handler based on signal.type.
    """
    handlers = {
        SignalType.DECISION: handle_decision,
        SignalType.REQUEST_INPUT: handle_request_input,
        SignalType.PROGRESS: handle_progress,
        SignalType.SKIP_PHASE: handle_skip_phase,
        SignalType.ADD_ROADMAP: handle_add_roadmap,
    }
    handler = handlers.get(signal.type)
    if not handler:
        raise HTTPException(400, f"Unknown signal type: {signal.type}")
    return await handler(signal)

async def handle_request_input(signal: BackendSignal):
    """
    Pause workflow and wait for human input.
    1. Set workflow state to WAITING_FOR_INPUT
    2. Emit TUI event to show input modal
    3. Block until user responds (or timeout)
    4. Return user's choice to backend
    """
    # Get the workflow orchestrator for this project
    orchestrator = get_orchestrator(signal.project_id)
    
    # Pause the workflow
    orchestrator.pause(reason="waiting_for_input")
    
    # Create a Future that will be resolved when user responds
    response_future = asyncio.Future()
    pending_inputs[signal.project_id] = response_future
    
    # Emit event to TUI
    emit_event("request_input", {
        "project_id": signal.project_id,
        "question": signal.payload["question"],
        "options": signal.payload.get("options"),
    })
    
    # Wait for response (with timeout)
    try:
        timeout = signal.payload.get("timeout_seconds", 300)
        response = await asyncio.wait_for(response_future, timeout)
        return {"status": "ok", "response": response}
    except asyncio.TimeoutError:
        return {"status": "timeout", "response": None}
```

#### Step 3: MCP Server (`src/agent_pump/communication/mcp_server.py`)

Use the `mcp` Python package (install: `uv add mcp`):

```python
from mcp.server import Server
from mcp.types import Tool, Resource

class AgentPumpMCPServer:
    def __init__(self, orchestrator_registry):
        self.server = Server("agent-pump")
        self.orchestrator_registry = orchestrator_registry
        self._register_tools()
        self._register_resources()
    
    def _register_tools(self):
        @self.server.tool("signal_decision")
        async def signal_decision(
            project_id: str,
            decision: str,
            confidence: float,
            reasoning: str = ""
        ) -> str:
            """Report a decision with confidence score."""
            # Same logic as HTTP callback
            ...
        
        @self.server.tool("request_human_input")
        async def request_human_input(
            project_id: str,
            question: str,
            options: list[str] | None = None
        ) -> str:
            """Pause workflow and ask the user a question."""
            ...
        
        @self.server.tool("report_progress")
        async def report_progress(
            project_id: str,
            percent: int,
            message: str
        ) -> str:
            """Report progress to the TUI."""
            ...
        
        @self.server.tool("add_roadmap_item")
        async def add_roadmap_item(
            project_id: str,
            title: str,
            description: str,
            priority: str = "medium"
        ) -> str:
            """Add a new item to the project's ROADMAP.md."""
            ...
    
    def _register_resources(self):
        @self.server.resource("agent_pump://roadmap/{project_id}")
        async def get_roadmap(project_id: str) -> str:
            """Return the parsed ROADMAP.md content."""
            project = self.orchestrator_registry.get_project(project_id)
            return project.read_roadmap()
        
        @self.server.resource("agent_pump://workflow_state/{project_id}")
        async def get_workflow_state(project_id: str) -> str:
            """Return current workflow state as JSON."""
            orchestrator = self.orchestrator_registry.get(project_id)
            return orchestrator.state.model_dump_json()
    
    async def start(self, transport="stdio"):
        """Start the MCP server."""
        if transport == "stdio":
            await self.server.run_stdio()
        elif transport == "sse":
            # For HTTP SSE transport
            await self.server.run_sse(host="localhost", port=3333)
```

#### Step 4: Inject Config into Backends (`src/agent_pump/communication/injection.py`)

Before invoking a backend, inject the communication config:

```python
import os
import json
from pathlib import Path

def inject_communication_config(
    project_id: str,
    backend_type: str,
    callback_url: str,
    mcp_port: int = 3333
) -> dict[str, str]:
    """
    Returns environment variables to inject into the backend process.
    Also writes MCP config files for backends that need them.
    """
    env = {
        "AGENT_PUMP_CALLBACK_URL": callback_url,
        "AGENT_PUMP_PROJECT_ID": project_id,
        "AGENT_PUMP_MCP_PORT": str(mcp_port),
    }
    
    # For Gemini CLI: write to ~/.gemini/settings.json
    if backend_type == "gemini":
        gemini_config = Path.home() / ".gemini" / "settings.json"
        config = json.loads(gemini_config.read_text()) if gemini_config.exists() else {}
        config.setdefault("mcpServers", {})
        config["mcpServers"]["agent-pump"] = {
            "url": f"http://localhost:{mcp_port}/sse"
        }
        gemini_config.write_text(json.dumps(config, indent=2))
    
    # For Claude: write to ~/.claude/mcp_servers.json  
    elif backend_type == "claude":
        claude_config = Path.home() / ".claude" / "mcp_servers.json"
        config = json.loads(claude_config.read_text()) if claude_config.exists() else {}
        config["agent-pump"] = {
            "command": "npx",  # or direct connection
            "args": ["-y", "mcp-client", f"http://localhost:{mcp_port}/sse"]
        }
        claude_config.write_text(json.dumps(config, indent=2))
    
    return env
```

#### Step 5: Update Backend Base Class (`src/agent_pump/backends/base.py`)

Modify the base backend to use injection:

```python
# In BackendBase.invoke() method:
async def invoke(self, prompt: str, project: Project) -> BackendResult:
    # Inject communication config
    from agent_pump.communication.injection import inject_communication_config
    
    extra_env = inject_communication_config(
        project_id=project.id,
        backend_type=self.backend_type,
        callback_url=f"http://localhost:{self.api_port}/api/callback",
        mcp_port=self.mcp_port,
    )
    
    # Merge with existing env
    env = {**os.environ, **extra_env}
    
    # Run the backend process with injected env
    process = await asyncio.create_subprocess_exec(
        *self.command,
        env=env,
        ...
    )
```

#### Step 6: TUI Integration (`src/agent_pump/tui/screens/input_request_modal.py`)

Create a modal that appears when backend requests input:

```python
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioSet, RadioButton

class InputRequestModal(ModalScreen):
    """Modal shown when backend requests human input."""
    
    def __init__(self, question: str, options: list[str] | None, callback):
        super().__init__()
        self.question = question
        self.options = options
        self.callback = callback
    
    def compose(self):
        yield Label(self.question, id="question")
        if self.options:
            with RadioSet(id="options"):
                for opt in self.options:
                    yield RadioButton(opt)
        else:
            yield Input(id="free_text")
        yield Button("Submit", id="submit", variant="primary")
    
    def on_button_pressed(self, event):
        if event.button.id == "submit":
            if self.options:
                response = self.query_one(RadioSet).pressed_button.label
            else:
                response = self.query_one("#free_text").value
            self.callback(response)
            self.dismiss()
```

#### Testing Strategy

1. **Unit tests**: Mock the HTTP endpoints and test signal routing
2. **Integration tests**: Spin up MCP server, connect a mock client, verify tools work
3. **E2E tests**: Run a real backend (in dry-run mode) and verify it can call back

#### Dependencies

- `mcp` - MCP Python SDK (`uv add mcp`)
- Existing: `fastapi`, `pydantic`, `textual`

---

## Future Sprints

### 🔴 Scheduled Workflow Runs
**Priority: Medium**

Cron-like scheduling for hands-free automation.

#### Implementation Overview

```
src/agent_pump/
├── scheduling/
│   ├── __init__.py
│   ├── scheduler.py         # APScheduler wrapper
│   ├── schedule_config.py   # Pydantic models
│   └── schedule_service.py  # CRUD operations
├── models/
│   └── schedule.py          # Schedule model
```

#### Step 1: Add Dependency

```bash
uv add apscheduler>=4.0
```

#### Step 2: Define Schedule Model (`src/agent_pump/models/schedule.py`)

```python
from pydantic import BaseModel
from datetime import datetime, time
from enum import Enum

class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"

class Schedule(BaseModel):
    id: str
    project_id: str
    enabled: bool = True
    schedule_type: ScheduleType
    
    # For cron: "0 2 * * *" (2 AM daily)
    cron_expression: str | None = None
    
    # For interval: run every N minutes/hours
    interval_minutes: int | None = None
    
    # For one-time: specific datetime
    run_at: datetime | None = None
    
    # Constraints
    timezone: str = "America/Chicago"
    working_hours_only: bool = False
    working_hours_start: time = time(9, 0)
    working_hours_end: time = time(17, 0)
    max_queue_depth: int = 3  # Don't queue more than N runs
    
    # Metadata
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
```

#### Step 3: Scheduler Service (`src/agent_pump/scheduling/scheduler.py`)

```python
from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

class WorkflowScheduler:
    def __init__(self, orchestrator_registry):
        self.scheduler = AsyncScheduler()
        self.orchestrator_registry = orchestrator_registry
        self.schedules: dict[str, Schedule] = {}
    
    async def start(self):
        await self.scheduler.start()
        # Load saved schedules from disk
        await self._load_schedules()
    
    async def add_schedule(self, schedule: Schedule):
        trigger = self._create_trigger(schedule)
        
        await self.scheduler.add_job(
            self._run_workflow,
            trigger=trigger,
            id=schedule.id,
            kwargs={"project_id": schedule.project_id}
        )
        self.schedules[schedule.id] = schedule
        await self._save_schedules()
    
    async def _run_workflow(self, project_id: str):
        """Called by scheduler when it's time to run."""
        schedule = self._get_schedule_for_project(project_id)
        
        # Check working hours constraint
        if schedule.working_hours_only:
            if not self._is_working_hours(schedule):
                return  # Skip this run
        
        # Check queue depth
        orchestrator = self.orchestrator_registry.get(project_id)
        if orchestrator.queue_depth >= schedule.max_queue_depth:
            return  # Too many queued, skip
        
        # Start the workflow
        await orchestrator.start()
    
    def _create_trigger(self, schedule: Schedule):
        if schedule.schedule_type == ScheduleType.CRON:
            return CronTrigger.from_crontab(
                schedule.cron_expression,
                timezone=schedule.timezone
            )
        elif schedule.schedule_type == ScheduleType.INTERVAL:
            return IntervalTrigger(minutes=schedule.interval_minutes)
```

#### Step 4: TUI Calendar View (`src/agent_pump/tui/screens/schedule_modal.py`)

```python
class ScheduleModal(ModalScreen):
    """Configure scheduled runs for a project."""
    
    def compose(self):
        yield Label("Schedule Workflow Runs", classes="title")
        yield Select(
            options=[
                ("Daily at 2 AM", "0 2 * * *"),
                ("Every 6 hours", "interval:360"),
                ("Weekdays at midnight", "0 0 * * 1-5"),
                ("Custom...", "custom"),
            ],
            id="schedule_preset"
        )
        yield Input(placeholder="Custom cron: 0 2 * * *", id="custom_cron")
        yield Checkbox("Only during working hours", id="working_hours")
        yield Input(value="3", id="max_queue", type="integer")
        yield Button("Save Schedule", id="save")
```

#### Step 5: CLI Commands

```bash
uv run agent-pump schedule list
uv run agent-pump schedule add ./my-project --cron "0 2 * * *"
uv run agent-pump schedule add ./my-project --interval 360  # every 6 hours
uv run agent-pump schedule remove <schedule-id>
uv run agent-pump schedule enable/disable <schedule-id>
```

---

### 🔴 GitHub Issue Sync
**Priority: Medium**

Automatically sync GitHub Issues with ROADMAP.md.

#### Implementation Overview

```
src/agent_pump/
├── integrations/
│   ├── __init__.py
│   ├── github_client.py     # PyGithub wrapper
│   ├── issue_sync.py        # Sync logic
│   └── issue_mapper.py      # Issue <-> Roadmap mapping
├── models/
│   └── github_config.py     # Config model
```

#### Step 1: Add Dependency

```bash
uv add PyGithub
```

#### Step 2: GitHub Config Model (`src/agent_pump/models/github_config.py`)

```python
class GitHubSyncConfig(BaseModel):
    enabled: bool = False
    repo: str  # "owner/repo"
    token: str  # GitHub PAT (store securely!)
    
    # Filtering
    sync_labels: list[str] = ["agent-pump"]  # Only sync issues with these labels
    ignore_labels: list[str] = ["wontfix", "duplicate"]
    
    # Mapping
    priority_map: dict[str, str] = {
        "priority:high": "High",
        "priority:medium": "Medium",
        "priority:low": "Low",
    }
    
    # Behavior
    auto_close_on_complete: bool = True
    sync_direction: str = "bidirectional"  # "github_to_roadmap", "roadmap_to_github", "bidirectional"
    sync_interval_minutes: int = 30
```

#### Step 3: Issue Sync Service (`src/agent_pump/integrations/issue_sync.py`)

```python
from github import Github

class GitHubIssueSync:
    def __init__(self, config: GitHubSyncConfig, roadmap_service):
        self.github = Github(config.token)
        self.repo = self.github.get_repo(config.repo)
        self.config = config
        self.roadmap_service = roadmap_service
    
    async def sync(self):
        """
        Main sync loop:
        1. Fetch open issues from GitHub with matching labels
        2. Compare with ROADMAP.md items
        3. Create missing items in roadmap
        4. Close issues for completed roadmap items
        """
        issues = self._fetch_issues()
        roadmap_items = self.roadmap_service.get_all_items()
        
        # GitHub -> Roadmap
        for issue in issues:
            if not self._find_roadmap_item(issue, roadmap_items):
                self._create_roadmap_item(issue)
        
        # Roadmap -> GitHub (close completed)
        if self.config.auto_close_on_complete:
            for item in roadmap_items:
                if item.status == "completed":
                    issue = self._find_github_issue(item)
                    if issue and issue.state == "open":
                        issue.edit(state="closed")
                        issue.create_comment(
                            "✅ Closed by Agent Pump - feature completed!"
                        )
    
    def _fetch_issues(self):
        labels = self.config.sync_labels
        return self.repo.get_issues(state="open", labels=labels)
    
    def _create_roadmap_item(self, issue):
        priority = self._map_priority(issue.labels)
        self.roadmap_service.add_item(
            title=issue.title,
            description=issue.body,
            priority=priority,
            metadata={"github_issue": issue.number}
        )
```

#### Step 4: Webhook Handler (for real-time sync)

Add to existing FastAPI server:

```python
@router.post("/webhooks/github")
async def github_webhook(request: Request):
    payload = await request.json()
    event = request.headers.get("X-GitHub-Event")
    
    if event == "issues":
        action = payload["action"]
        if action in ("opened", "edited", "labeled"):
            await issue_sync.sync_single_issue(payload["issue"])
        elif action == "closed":
            await issue_sync.mark_roadmap_complete(payload["issue"])
```

---

### 🔴 Automatic PR Creation
**Priority: Medium**

Auto-create PRs after successful commits.

#### Implementation Overview

```
src/agent_pump/
├── integrations/
│   └── pr_creator.py        # PR creation logic
├── models/
│   └── pr_config.py         # Configuration
```

#### Step 1: PR Config Model

```python
class PRCreationConfig(BaseModel):
    enabled: bool = False
    create_draft: bool = True  # Draft PR for review
    auto_assign_reviewers: bool = True
    
    # Templates
    title_template: str = "[Agent Pump] {feature_title}"
    body_template: str = """
## Summary
{engineering_plan_summary}

## Changes
{commit_messages}

## Verification
{verification_results}

---
*Created automatically by Agent Pump*
"""
```

#### Step 2: PR Creator Service

```python
class PRCreator:
    def __init__(self, github_client, config: PRCreationConfig):
        self.github = github_client
        self.config = config
    
    async def create_pr(
        self,
        project: Project,
        feature_branch: str,
        base_branch: str = "main"
    ) -> str:
        """Create a PR and return the URL."""
        # Gather context
        plan = project.read_file("ENGINEERING_PLAN.md")
        commits = self._get_branch_commits(feature_branch, base_branch)
        verification = project.last_verification_result
        
        # Build PR content
        title = self.config.title_template.format(
            feature_title=self._extract_feature_title(plan)
        )
        body = self.config.body_template.format(
            engineering_plan_summary=self._summarize_plan(plan),
            commit_messages=self._format_commits(commits),
            verification_results=self._format_verification(verification),
        )
        
        # Create PR
        repo = self.github.get_repo(project.github_repo)
        pr = repo.create_pull(
            title=title,
            body=body,
            head=feature_branch,
            base=base_branch,
            draft=self.config.create_draft,
        )
        
        # Assign reviewers
        if self.config.auto_assign_reviewers:
            reviewers = await self._get_reviewers(project)
            pr.create_review_request(reviewers=reviewers)
        
        return pr.html_url
```

#### Step 3: Integration with Workflow

In `src/agent_pump/orchestrator/workflow.py`, after the commit phase:

```python
async def _after_commit_phase(self, project: Project):
    if project.config.pr_creation.enabled:
        if project.branch_strategy.enabled:
            pr_url = await self.pr_creator.create_pr(
                project=project,
                feature_branch=project.current_branch,
                base_branch=project.branch_strategy.base_branch,
            )
            self.log(f"Created PR: {pr_url}")
```

---

### 🔴 Webhook Triggers
**Priority: Medium**

Start workflows from external events.

#### Implementation Overview

```
src/agent_pump/
├── api/
│   └── webhooks.py          # Webhook endpoints
├── models/
│   └── webhook_config.py    # Security config
```

#### Step 1: Webhook Config

```python
class WebhookConfig(BaseModel):
    enabled: bool = False
    secret_key: str  # For HMAC validation
    allowed_sources: list[str] = ["github", "slack", "custom"]
    
class WebhookTrigger(BaseModel):
    source: str  # "github", "slack", "custom"
    event_type: str  # "push", "issue_comment", "slash_command"
    project_id: str | None  # Specific project, or None for routing
    phase: str | None  # Start at specific phase
```

#### Step 2: Webhook Endpoints

```python
@router.post("/webhooks/trigger/{source}")
async def webhook_trigger(
    source: str,
    request: Request,
    x_signature: str = Header(None)
):
    # Validate signature
    body = await request.body()
    if not validate_hmac(body, x_signature, config.secret_key):
        raise HTTPException(401, "Invalid signature")
    
    payload = await request.json()
    
    # Route to appropriate handler
    if source == "github":
        return await handle_github_webhook(payload, request.headers)
    elif source == "slack":
        return await handle_slack_webhook(payload)
    else:
        return await handle_custom_webhook(payload)

async def handle_github_webhook(payload, headers):
    event = headers.get("X-GitHub-Event")
    
    if event == "issue_comment":
        # Check for trigger phrase like "/agent-pump run"
        comment = payload["comment"]["body"]
        if comment.startswith("/agent-pump"):
            command = parse_command(comment)
            await execute_command(command, payload)
    
    elif event == "push":
        # Auto-trigger on push to specific branches
        branch = payload["ref"].split("/")[-1]
        if branch in config.auto_trigger_branches:
            project = find_project_by_repo(payload["repository"]["full_name"])
            await orchestrator.start(project)
```

#### Step 3: Slack Integration

```python
async def handle_slack_webhook(payload):
    """Handle Slack slash commands like /agent-pump start my-project"""
    command = payload.get("command")
    text = payload.get("text", "").split()
    
    if command == "/agent-pump":
        action = text[0] if text else "status"
        project_name = text[1] if len(text) > 1 else None
        
        if action == "start":
            project = find_project_by_name(project_name)
            await orchestrator.start(project)
            return {"text": f"Started workflow for {project_name}"}
        elif action == "status":
            return {"text": format_status_for_slack()}
```

---

### 🔴 Auto-Fix CI Failures
**Priority: Medium**

Automatically respond when CI pipelines fail.

#### Implementation Overview

```
src/agent_pump/
├── integrations/
│   ├── ci_watcher.py        # Poll/webhook for CI status
│   ├── failure_parser.py    # Parse CI logs
│   └── auto_fix.py          # Create fix tasks
```

#### Step 1: CI Watcher Service

```python
class CIWatcher:
    def __init__(self, github_client, orchestrator_registry):
        self.github = github_client
        self.orchestrator_registry = orchestrator_registry
        self.retry_tracker: dict[str, int] = {}  # run_id -> retry_count
    
    async def handle_check_run(self, payload):
        """Called when GitHub Actions check completes."""
        if payload["action"] != "completed":
            return
        
        check_run = payload["check_run"]
        if check_run["conclusion"] == "failure":
            await self._handle_failure(check_run, payload["repository"])
    
    async def _handle_failure(self, check_run, repo):
        run_id = check_run["id"]
        
        # Check retry count
        retries = self.retry_tracker.get(run_id, 0)
        if retries >= 3:
            self.log(f"Max retries reached for {run_id}, giving up")
            return
        
        # Parse failure logs
        logs = await self._fetch_logs(check_run)
        failure_info = self.failure_parser.parse(logs)
        
        # Create fix task
        project = self._find_project(repo["full_name"])
        await self._create_fix_task(project, failure_info)
        
        # Trigger workflow
        self.retry_tracker[run_id] = retries + 1
        await self.orchestrator_registry.get(project.id).start()
```

#### Step 2: Failure Parser

```python
class FailureParser:
    """Parse CI logs to extract actionable failure info."""
    
    PATTERNS = [
        # Python
        (r"(\w+Error): (.+)", "python_error"),
        (r"FAILED (.+\.py)::(\w+)", "pytest_failure"),
        
        # JavaScript
        (r"error TS(\d+): (.+)", "typescript_error"),
        (r"✕ (.+)", "jest_failure"),
        
        # Rust
        (r"error\[E(\d+)\]: (.+)", "rust_error"),
        
        # Generic
        (r"error: (.+)", "generic_error"),
    ]
    
    def parse(self, logs: str) -> FailureInfo:
        errors = []
        for pattern, error_type in self.PATTERNS:
            matches = re.findall(pattern, logs)
            for match in matches:
                errors.append({"type": error_type, "details": match})
        
        return FailureInfo(
            errors=errors,
            raw_log=logs[-5000:],  # Last 5K chars
            suggested_fix=self._suggest_fix(errors),
        )
    
    def _suggest_fix(self, errors) -> str:
        # Simple heuristics for common errors
        for error in errors:
            if error["type"] == "python_error" and "ModuleNotFound" in str(error["details"]):
                return "Install missing dependency"
            if error["type"] == "typescript_error":
                return "Fix TypeScript type errors"
        return "Review and fix failing tests"
```

#### Step 3: Integration

The Auto-Fix service creates a special roadmap item:

```python
async def _create_fix_task(self, project: Project, failure_info: FailureInfo):
    roadmap_service = RoadmapService(project)
    
    # Add to top of current sprint
    roadmap_service.add_item(
        title=f"🔧 Fix CI Failure: {failure_info.suggested_fix}",
        description=f"""
## CI Failure Details

**Errors Found:**
{self._format_errors(failure_info.errors)}

**Suggested Approach:**
{failure_info.suggested_fix}

**Raw Log (last 500 chars):**
```
{failure_info.raw_log[-500:]}
```

---
*Auto-generated by Agent Pump CI Watcher*
""",
        priority="High",
        position="top",  # Insert at top of sprint
        metadata={
            "auto_generated": True,
            "ci_run_id": failure_info.run_id,
            "retry_count": self.retry_tracker.get(failure_info.run_id, 0),
        }
    )
```

---

## Deferred Features

### ⚫ Template Library Marketplace
**Priority: Low**

Shared template repository for community templates:
- Download/install templates from remote sources
- Template ratings and reviews
- Category-based template browsing
- Automatic updates for installed templates

---

### ⚫ AI Code Review Integration
**Priority: Low**

Advanced automated code review capabilities:
- Automated review suggestions after implementation
- Security vulnerability detection patterns
- Performance optimization hints
- Language-specific best practice enforcement

---

### ⚫ Git History Analysis
**Priority: Low**

Learn from project history to improve workflows:
- Analyze commit patterns for workflow improvement
- Suggest optimal branch strategies based on history
- Identify potential merge conflicts early
- Predict feature completion time based on past velocity

---

### ⚫ Collaborative Mode
**Priority: Low**

Team collaboration features:
- Share workspace with team members
- Real-time collaboration on features
- Conflict resolution for simultaneous edits
- Team-wide metrics and analytics

---

## Notes for AI Agents

When processing this roadmap:
1. Select the first 🔴 **Not Started** item under "Current Sprint"
2. Create `ENGINEERING_PLAN.md` with detailed implementation steps
3. After implementation, update status to 🟡 then document in `docs/features.md`
4. Remove completed items from this file (they live in docs/features.md)
5. During brainstorm phase, add new valuable features
   - When adding a new feature, add it to the roadmap with a 🔴 status
   - When current sprint is empty, select the first 🔴 item and move it to current sprint and expand upon it with more details.
6. When committing:
   - Use `git add <specific-file>` for each changed file
   - NEVER use `git add .` or `git add -A`
   - Write clear commit messages
