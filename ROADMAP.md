# Agent Pump - Roadmap

This document tracks feature development for Agent Pump. Items are processed in order.

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- 🟢 **Complete** - Implemented and verified
- ⚫ **Deferred** - Postponed for later consideration

---

## Recently Completed

### 🟢 Backend Fallback Chains
**Completed: 2026-01-11**

Automatic fallback when primary backend fails or hits quota limits.

- Fallback on unavailability, quota errors, or exceptions
- Per-backend custom CLI args (e.g., `--model gemini-2.5-flash`)
- TUI modal for configuration (`b` key)

---

### 🟢 Prompt Customization
**Completed: 2026-01-11**

Per-project, per-phase prompt prefix/suffix overrides.

- Prefix added before standard prompt, suffix after
- TUI modal for configuration (`p` key)
- Saved to workspace config

---

### 🟢 Workspace Configuration
**Completed: 2026-01-11**

Persistent workspace configuration with project settings.

- Multiple workspaces with `workspace create/switch`
- Idea queue for brainstormer (`i` key to add)
- Phase-specific backend configuration

---

## Current Sprint

### 🔴 Custom Verification Commands
**Priority: Medium**

Support project-specific build, lint, and test commands via configuration.

**Acceptance Criteria:**
- Read commands from `.agent-pump.yml`
- Auto-detect common patterns (npm, cargo, go, uv, etc.)
- Report verification results clearly
- Allow skipping verification phases

---

## Future Enhancements

### 🔴 Copy Config Between Projects
**Priority: Medium**

Allow copying backend/prompt configuration from one project to another.

**Acceptance Criteria:**
- "Copy from..." button in config modals
- Select source project from dropdown
- Option to copy to all projects (workspace default)

---

### 🔴 Claude Code Backend
**Priority: Medium**

Implement backend for Anthropic's Claude Code CLI.

**Acceptance Criteria:**
- Detect Claude Code installation
- Map prompts to Claude Code CLI flags
- Stream output to TUI
- Handle authentication

---

### 🔴 OpenCode Backend
**Priority: Medium**

Implement backend for OpenCode CLI.

**Acceptance Criteria:**
- Detect OpenCode installation
- Map prompts to OpenCode CLI flags
- Stream output to TUI

---

### 🔴 Progress Persistence & Resume
**Priority: Medium**

Save workflow state to disk and resume after interruption.

**Acceptance Criteria:**
- Persist state to `.agent-pump/state.json`
- Resume from last successful phase
- Handle stale state gracefully
- Option to reset state

---

### 🔴 Notification System
**Priority: Low**

Send notifications on feature completion, errors, or when human intervention is needed.

**Acceptance Criteria:**
- Desktop notifications (optional)
- Webhook support for Slack/Discord
- Configurable notification levels

---

### 🔴 Feature Prioritization
**Priority: Medium**

Allow users to prioritize which roadmap items are worked on next via the TUI.

**Acceptance Criteria:**
- List all uncompleted roadmap items in a dedicated TUI view
- Support moving items up/down the list (k/j keys or dragging)
- Persistent reordering of ROADMAP.md based on user selection
- Orchestrator respects the new order

---

### 🔴 Analytics Dashboard
**Priority: Low**

Track metrics like features completed, time per phase, success/failure rates.

**Acceptance Criteria:**
- Store metrics in local SQLite
- Display charts in TUI
- Export to JSON/CSV
- Identify bottlenecks

---

### 🔴 Watch Mode
**Priority: Low**

Continuously monitor ROADMAP.md for new items and automatically start work.

**Acceptance Criteria:**
- File watcher on ROADMAP.md
- Detect new uncompleted items
- Auto-start workflow on changes
- Configurable poll interval

---

### 🔴 Graphical State Machine Visualization
**Priority: Low**

Render the workflow state machine as a graphical image (PNG/SVG) using pytransitions' GraphMachine and display in the TUI.

**Acceptance Criteria:**
- Use `transitions.extensions.GraphMachine` to generate state diagrams
- Requires Graphviz to be installed on the system
- Use `textual-image` library for terminal image display
- Fallback to ASCII diagram if image rendering fails
- Current state highlighted in the diagram
- Works across different terminal emulators (Sixel, TGP, Unicode fallback)

---

### 🔴 Git Hook Integration
**Priority: Low**

Automatically run verifications (lint, test) on pre-commit.

**Acceptance Criteria:**
- Install pre-commit hooks via CLI
- Run `uv run pytest` and `uv run ruff` before commit
- Prevent commit if verification fails
- Option to bypass hooks

---

### 🔴 Workflow Overview Dashboard
**Priority: Medium**

Overview all workflows in a single view.

**Acceptance Criteria:**
- Dashboard view showing all active workflows
- Summary status for each
- Quick navigation to details

---

### 🔴 Stop After Feature Option
**Priority: Medium**

Option to stop execution automatically after the current feature is completed.

**Acceptance Criteria:**
- Toggle in TUI or CLI flag
- Graceful shutdown after current feature verification
- No new tasks started from roadmap

---

### 🔴 Activity Log Preferences
**Priority: Low**

User preference to have new items added to the top of the activity log.

**Acceptance Criteria:**
- Configurable log order (ascending/descending)
- Persisted user preference
- TUI toggle or config file setting

---

### 🔴 Real-time State Visibility
**Priority: High**

Ability to see the current state of the machine while the machine is executing.

**Acceptance Criteria:**
- Live status indicator in TUI
- Shows current state (e.g., Planning, Implementing)
- Shows active substep or tool call if possible

---


---

### 🔴 Task Completion History
**Priority: Medium**

Save and display the history of completed tasks for each project.

**Acceptance Criteria:**
- Persistent record of completed tasks
- Date/time of completion
- View history in TUI

---

### 🔴 Project Persistence & Autoload
**Priority: Medium**

Remember previously loaded projects and automatically load them on startup.

**Acceptance Criteria:**
- Store list of active projects in config/state file
- Automatically load these projects when Agent Pump starts
- Handle missing paths gracefully
- Option to disable autoload

---

### 🔴 Web UI Interface
**Priority: Medium**

Host a web UI with a similar UX to the TUI when running the app. It should be a single page app and provide the same or similar functionality as the TUI.

**Acceptance Criteria:**
- Single Page Application (SPA) architecture
- UX consistent with Terminal UI
- Full functionality parity (monitoring, configuration, control)
- Hosted by the application during runtime

---

## Completed

*Features that have been implemented and verified.*

### 🟢 Dynamic Project Management
**Priority: High**

Enable adding and removing projects at runtime with concurrent execution.

**Acceptance Criteria:**
- Add projects via TUI or CLI
- Remove projects without affecting others
- Each project runs independently
- No artificial concurrency limits
- Project state persists

---

### 🟢 Basic TUI Dashboard
**Priority: High**

Create the initial Textual application with project status display, log viewer, and keyboard controls.

**Acceptance Criteria:**
- Display project cards with status
- Show real-time logs from agent
- Support add/remove project (a/r keys)
- Support pause/resume/skip commands
- Responsive layout for different terminal sizes

---

### 🟢 Workflow State Machine
**Priority: Critical**

Implement the 5-phase workflow (Plan → Implement → Verify → Brainstorm → Commit) with proper state transitions and persistence.

**Acceptance Criteria:**
- State persists across restarts
- Transitions validate preconditions
- Error states allow recovery
- Provides hooks for TUI updates
- Brainstorm phase happens BEFORE commit

---

### 🟢 Extensible Agent Backend System
**Priority: Critical**

Create the abstract base class for agent backends and implement the Gemini CLI backend. Design for easy addition of Claude Code, OpenCode, and other agents.

**Acceptance Criteria:**
- Abstract `AgentBackend` base class with clear interface
- `GeminiBackend` implementation with `--yolo`, `--checkpointing`, `--prompt` flags
- [x] Add `--verbose` flag for improved debug output
- Async streaming of agent output
- Backend availability detection
- Placeholder files for future backends (Claude, OpenCode)

---

### 🟢 Core Infrastructure
**Priority: Critical**

Set up the foundational project structure with uv, implement basic CLI entry point, and establish the module architecture.

**Acceptance Criteria:**
- Project initializes with `uv init`
- CLI runs with `uv run agent-pump --help`
- All dependencies install correctly
- Project structure matches implementation plan

---

## Deferred

*Features postponed for future consideration.*

---

### 🟢 Per-Project Activity Logs
**Priority: Medium**

Each project should have its own dedicated activity log.

**Acceptance Criteria:**
- Separate log storage per project
- TUI view switches logs based on selected project
- Global log vs Project log usage

---

## Notes for AI Agents

When processing this roadmap:
1. Select the first 🔴 **Not Started** item under "Current Sprint"
2. Create ENGINEERING_PLAN.md with detailed implementation steps
3. After implementation, update status to 🟢 **Complete**
4. Move completed items to the "Completed" section
5. During brainstorm phase, add new valuable features
6. When committing:
   - Use `git add <specific-file>` for each changed file
   - NEVER use `git add .` or `git add -A`
   - Do NOT add files in `.gemini/` directory
   - Write clear commit messages