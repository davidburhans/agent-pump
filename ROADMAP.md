# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint







---

### 🔴 Log Streaming Service
**Priority: Medium** | **Prerequisite for: Web Dashboard UI**

Extract log management into a reusable streaming service that both TUI and WebSocket endpoints can consume.

**Why this helps Web Dashboard:**
`LogPanel` in TUI handles log entries in memory with `log_entries: list[LogEntry]` and max size limits. The web UI needs the same log stream over WebSocket. A shared `LogBuffer` ensures consistent log storage, filtering, and streaming regardless of UI.

**Acceptance Criteria:**
- Create `src/agent_pump/services/log_service.py` with:
  - `LogBuffer` class with configurable max size
  - `add(entry: LogEntry)` method
  - `get_recent(n: int, filter: LogFilter | None)` method
  - `stream() -> AsyncIterator[LogEntry]` for WebSocket streaming
  - `clear()` method
- Per-project log buffers (already partially implemented)
- Refactor TUI `LogPanel` to use `LogBuffer`
- Support filtering by state, level, and task name
- Add unit tests for buffer behavior and streaming

---

### 🔴 Workflow State Snapshot Model
**Priority: Medium** | **Prerequisite for: Web Dashboard UI**

Standardize workflow state representation for consistent visualization across UIs.

**Why this helps Web Dashboard:**
Workflow state is scattered across `ProjectWorkflow.state`, `Project.state`, and rendered differently in different places (ASCII diagram, `WorkflowPanel`). The web UI needs canvas-based diagram rendering. A `WorkflowSnapshot` provides a single source of truth that both TUI's widget and web's canvas can consume for visualization.

**Acceptance Criteria:**
- Create `src/agent_pump/models/workflow_snapshot.py` with:
  - `WorkflowSnapshot` model containing:
    - `current_state`: str
    - `iteration`: int
    - `time_in_state`: float
    - `available_transitions`: list[str]
    - `nodes`: list[NodeSnapshot] (for diagram rendering)
    - `edges`: list[EdgeSnapshot] (for diagram rendering)
  - `NodeSnapshot`: name, is_active, is_completed, position
  - `EdgeSnapshot`: source, target, is_active
- Add `get_snapshot()` method to `ProjectWorkflow`
- Refactor TUI `WorkflowPanel` to consume snapshots
- Add tests for snapshot generation

---

### 🔴 HTTP Server Infrastructure
**Priority: Medium** | **Prerequisite for: Web Dashboard UI**

Set up the foundational web server infrastructure before building the full dashboard.

**Why this helps Web Dashboard:**
Setting up FastAPI, WebSocket handling, CORS, authentication, and static file serving from scratch during the web UI sprint adds complexity. Having infrastructure ready means the dashboard sprint focuses on features, not plumbing. Early setup also allows testing the API layer with the TUI.

**Acceptance Criteria:**
- Add FastAPI dependency to `pyproject.toml`
- Create `src/agent_pump/api/` module with:
  - `server.py`: FastAPI app with lifespan management
  - `routes/health.py`: `GET /health` endpoint
  - `routes/websocket.py`: WebSocket stub at `/ws`
  - `middleware/auth.py`: Basic auth middleware (configurable on/off)
  - `middleware/cors.py`: CORS configuration for local development
- Add `--web` flag to CLI to start HTTP server
- Add `--web-port` option (default: 8000)
- Server can run alongside TUI (separate process) or standalone
- Add startup/shutdown logging
- Document API structure in `docs/api.md`

---

### 🔴 Keybindings Manifest
**Priority: Low** | **Prerequisite for: Web Dashboard UI**

Extract keyboard shortcuts into a shared manifest that both TUI and Web UI can consume.

**Why this helps Web Dashboard:**
The roadmap specifies "same keyboard shortcuts work (where applicable)" for the web UI. Currently, shortcuts are hardcoded in `AgentPumpApp.BINDINGS`. A manifest allows the web UI to import the same definitions and render appropriate shortcuts, ensuring consistency.

**Acceptance Criteria:**
- Create `src/agent_pump/keybindings.py` with:
  - `Keybinding` model: key, action, label, description, web_available
  - `KEYBINDINGS` list of all application keybindings
- Refactor `AgentPumpApp.BINDINGS` to be generated from manifest
- Add `web_available: bool` flag to indicate shortcuts applicable to web
- Web UI can import and filter keybindings for help display
- Add tests to ensure TUI bindings match manifest

---

### 🔴 Web Dashboard UI
**Priority: High**

Host a web-based UI as a single-page application that mirrors TUI functionality, enabling remote monitoring and mobile access.

**Acceptance Criteria:**
- WebSocket-based real-time updates for project status and logs
- Create high-quality API documentation for the endpoints used by the web dashboard
- Responsive design for desktop and mobile browsers
- Same keyboard shortcuts work (where applicable)
- Authentication for remote access
- Run alongside or instead of TUI (`--web` flag)
- Use same backend as TUI (via Shared Service Layer)
- Canvas-based workflow state diagram rendering (using Workflow State Snapshot)

---

### 🔴 Multi-Workspace Management
**Priority: Medium**

Enable switching between multiple workspaces with different project sets and configurations.

**Acceptance Criteria:**
- `workspace list/create/switch/delete` CLI commands
- Quick workspace switcher in TUI (`W` key)
- Each workspace has independent project list and settings
- Workspace-specific backend and prompt defaults

---

### 🔴 Git Branch Strategy
**Priority: Medium**

Smart branch management for feature development to avoid cluttering the main branch.

**Acceptance Criteria:**
- Create feature branch before implementing (configurable)
- Branch naming convention from roadmap item (e.g., `feature/notification-system`)
- Option to auto-merge to main after verification passes
- Handle merge conflicts gracefully (pause and notify)

---

## Future Enhancements

### 🔴 Custom Workflow Editor
**Priority: High**

Allow users to fully customize the workflow: define phases, prompts, and transitions via an interactive editor.

**Acceptance Criteria:**
- Node-focused editor screen showing one workflow step at a time
- Configure per-node: name, description, prompts (system/user), timeout, retry behavior
- Define transitions between nodes (success path, failure path, skip conditions)
- Click on any node in the flow diagram to open it in the editor
- Save/load custom workflows as reusable templates
- Import/export workflow definitions as YAML/JSON
- Conditional transitions based on project state
- Workflow-level variables for being able to loop N times through a set of state transitions using conditional transitions

---

### 🔴 Performance Audit & Debuggability
**Priority: High**

Deep investigation and fixes for resource leaks, hangs, and performance issues.

**Acceptance Criteria:**
- Comprehensive audit of subprocess lifecycle management
- Memory profiling to identify leaks in long-running sessions
- Add structured logging with configurable verbosity levels
- Implement health check endpoint/command showing resource usage
- Timeout instrumentation to identify hanging operations
- Add `--debug` flag for verbose diagnostics without modifying config

---

### 🔴 Metrics & Analytics Dashboard
**Priority: Medium**

Track productivity metrics across projects and time.

**Acceptance Criteria:**
- Count completed features per day/week/month
- Track time spent in each workflow phase
- Success/failure rate for verification
- Export data as JSON/CSV

---

### 🔴 Project Templates
**Priority: Medium**

Quickly bootstrap new projects with pre-configured settings.

**Acceptance Criteria:**
- Save current project config as a template
- Apply template when adding new projects
- Built-in templates for common stacks (Python/uv, Node/npm, Rust/cargo)
- Template includes backend config, prompts, and verification commands

---

### 🔴 Dry Run Mode
**Priority: Medium**

Preview what the agent would do without making actual changes.

**Acceptance Criteria:**
- `--dry-run` flag shows planned actions without executing
- Display file changes as diffs before applying
- Estimate token usage and cost before running
- Useful for testing custom workflows and prompts

---

### 🔴 Checkpoint Rollback
**Priority: Medium**

Undo changes made by the agent and restore to a previous checkpoint.

**Acceptance Criteria:**
- Automatic checkpoints before each phase
- View list of checkpoints with timestamps and descriptions
- One-click rollback to any checkpoint (via git reset or file restore)
- Option to create manual checkpoints (`c` key in TUI)

---

### 🔴 Smart Context Window Management
**Priority: Medium**

Intelligently manage what context is sent to the agent to maximize effectiveness within token limits.

**Acceptance Criteria:**
- Analyze project size and prioritize relevant files
- Summarize large files instead of sending full content
- Track which files were recently modified by the agent
- Allow manual inclusion/exclusion of files from context
- Show estimated token usage before each phase

---

### 🔴 Parallel Project Execution Limits
**Priority: Low**

Control resource usage when running many projects simultaneously.

**Acceptance Criteria:**
- Configurable max concurrent project executions
- Queue projects when limit is reached
- Priority ordering for queued projects
- Per-project resource limits (CPU, memory hints for backends)

---

### 🔴 Cost Tracking & Budgets
**Priority: Low**

Track API costs and set spending limits per project or globally.

**Acceptance Criteria:**
- Estimate token usage per phase and convert to cost
- Cumulative cost display per project and workspace
- Set daily/weekly/monthly budget limits
- Pause execution when budget is exceeded (configurable)
- Export cost reports

---

### 🔴 Approval Gates
**Priority: Low**

Require human approval at configurable points in the workflow.

**Acceptance Criteria:**
- Define gates between any phases (e.g., require approval before committing)
- Desktop/mobile notification when approval is needed
- Review diff and logs before approving
- Timeout behavior (auto-reject, auto-approve, or wait indefinitely)
- Batch approval for multiple pending projects

---

### 🔴 Collaborative Mode
**Priority: Low**

Enable multiple users to monitor and interact with the same Agent Pump instance.

**Acceptance Criteria:**
- Shared state via web dashboard
- User identification for idea injection
- Activity log shows who injected which ideas
- Role-based permissions (viewer vs controller)

---

### 🔴 Plugin System
**Priority: Low**

Allow extending Agent Pump with custom phases, backends, or hooks.

**Acceptance Criteria:**
- Python-based plugin API
- Hook into workflow events (pre/post phase)
- Custom verification steps
- Community plugin registry (future)

---

## Deferred

*Features postponed for later consideration.*

### ⚫ Voice Control
**Priority: Low**

Voice commands for hands-free operation.

**Rationale for Deferral:** Requires significant additional dependencies and platform-specific audio handling. Consider after core features stabilize.

---

### ⚫ IDE Extensions
**Priority: Low**

VS Code and JetBrains extensions for in-editor integration.

**Rationale for Deferral:** Large scope requiring maintenance of multiple extension codebases. Consider after web dashboard is stable.

---

## Notes for AI Agents

When processing this roadmap:
1. Select the first 🔴 **Not Started** item under "Current Sprint"
2. Create `ENGINEERING_PLAN.md` with detailed implementation steps
3. After implementation, update status to 🟡 then document in `FEATURES.md`
4. Remove completed items from this file (they live in FEATURES.md)
5. During brainstorm phase, add new valuable features
6. When committing:
   - Use `git add <specific-file>` for each changed file
   - NEVER use `git add .` or `git add -A`
   - Do NOT add files in `.gemini/` directory
   - Write clear commit messages