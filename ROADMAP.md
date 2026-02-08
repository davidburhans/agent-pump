# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

(No items currently)

## Future Sprints

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

---

### 🔴 File Watcher Trigger
**Priority: Low**

Trigger workflows automatically when files change.

#### Implementation Overview

- **Watcher**: Use `watchfiles` to monitor project directory.
- **Debounce**: Wait for changes to settle before triggering.
- **Filters**: Ignore `.git`, `__pycache__`, etc.
- **Action**: Trigger verification or full workflow on change.

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

### 🔴 Code Coverage Integration
**Priority: Medium**

Visualize code coverage directly in the TUI and use it as a verification gate.

#### Implementation Overview

- **Coverage Collection**: Run tests with coverage (e.g. `pytest --cov`, `cargo tarpaulin`).
- **Parsing**: Parse standard coverage formats (Cobertura XML, LCOV, JSON).
- **TUI Visualization**:
    - Project-wide coverage percentage in dashboard.
    - File-level coverage in diff viewer or file browser.
    - Heatmap visualization for specific files.
- **Verification Gate**: Fail verification if coverage drops below threshold.
- **Agent Context**: Feed coverage gaps to the agent to suggest missing tests.

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
3. After implementation, update status to 🟡 then document in `FEATURES.md`
4. Remove completed items from this file (they live in FEATURES.md)
5. During brainstorm phase, add new valuable features
   - When adding a new feature, add it to the roadmap with a 🔴 status
   - When current sprint is empty, select the first 🔴 item and move it to current sprint and expand upon it with more details.
6. When committing:
   - Use `git add <specific-file>` for each changed file
   - NEVER use `git add .` or `git add -A`
   - Write clear commit messages

### 🔴 Enhanced Tool Security
**Priority: Medium**

Add security controls for custom tools execution.

#### Implementation Overview

- **Allow/Deny Lists**: Configure allowed commands and paths.
- **Argument Validation**: Enhanced regex and type validation for tool arguments.
- **Sandboxing**: Optional execution in isolated environments (e.g. Docker).

---

### 🔴 Remote MCP Server Support
**Priority: Low**

Connect to external MCP servers to extend capabilities beyond local tools.

#### Implementation Overview

- **Client Integration**: Add MCP client capabilities to Agent Pump.
- **Configuration**: Define remote servers in `config.yml`.
- **Proxying**: Expose remote tools to the internal agent loop.

### 🔴 Ollama Backend Support
**Priority: Medium**

Add native support for Ollama to run local models easily.

#### Implementation Overview

- **Backend Class**: `src/agent_pump/backends/ollama.py`
- **Configuration**: Endpoint URL (default http://localhost:11434), model name.
- **Integration**: Add to `BackendFactory`.
- **Streaming**: Support streaming responses for real-time feedback.
