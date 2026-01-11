# Agent Pump - Roadmap

This document tracks feature development for Agent Pump. Items are processed in order.

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- 🟢 **Complete** - Implemented and verified
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

### 🔴 Core Infrastructure
**Priority: Critical**

Set up the foundational project structure with uv, implement basic CLI entry point, and establish the module architecture.

**Acceptance Criteria:**
- Project initializes with `uv init`
- CLI runs with `uv run agent-pump --help`
- All dependencies install correctly
- Project structure matches implementation plan

---

### 🔴 Extensible Agent Backend System
**Priority: Critical**

Create the abstract base class for agent backends and implement the Gemini CLI backend. Design for easy addition of Claude Code, OpenCode, and other agents.

**Acceptance Criteria:**
- Abstract `AgentBackend` base class with clear interface
- `GeminiBackend` implementation with `--yolo`, `--checkpointing`, `--prompt` flags
- Async streaming of agent output
- Backend availability detection
- Placeholder files for future backends (Claude, OpenCode)

---

### 🔴 Workflow State Machine
**Priority: Critical**

Implement the 5-phase workflow (Plan → Implement → Verify → Brainstorm → Commit) with proper state transitions and persistence.

**Acceptance Criteria:**
- State persists across restarts
- Transitions validate preconditions
- Error states allow recovery
- Provides hooks for TUI updates
- Brainstorm phase happens BEFORE commit

---

### 🔴 Basic TUI Dashboard
**Priority: High**

Create the initial Textual application with project status display, log viewer, and keyboard controls.

**Acceptance Criteria:**
- Display project cards with status
- Show real-time logs from agent
- Support add/remove project (a/r keys)
- Support pause/resume/skip commands
- Responsive layout for different terminal sizes

---

### 🔴 Dynamic Project Management
**Priority: High**

Enable adding and removing projects at runtime with concurrent execution.

**Acceptance Criteria:**
- Add projects via TUI or CLI
- Remove projects without affecting others
- Each project runs independently
- No artificial concurrency limits
- Project state persists

---

## Future Enhancements

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

### 🔴 Custom Verification Commands
**Priority: Medium**

Support project-specific build, lint, and test commands via configuration.

**Acceptance Criteria:**
- Read commands from `.agent-pump.yml`
- Auto-detect common patterns (npm, cargo, go, uv, etc.)
- Report verification results clearly
- Allow skipping verification phases

---

### 🔴 Notification System
**Priority: Low**

Send notifications on feature completion, errors, or when human intervention is needed.

**Acceptance Criteria:**
- Desktop notifications (optional)
- Webhook support for Slack/Discord
- Configurable notification levels

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

## Completed

*Features that have been implemented and verified.*

---

## Deferred

*Features postponed for future consideration.*

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
