# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

### 🟡 Global Backend Configuration
**Priority: High**

Refactor backend configuration to be defined at the global or project level.
- Configure available backends (e.g., "production-gemini", "experimental-opencode") at project/global level
- Workflow states simply select from pre-defined backends
- Allow states to specify one-off backends if needed
- Reduces duplication and simplifies configuration management

### 🟡 OpenCode API Backend
**Priority: Medium**

Add a backend that uses the [opencode-sdk-python](https://github.com/anomalyco/opencode-sdk-python) library.
- Library is already added as a dependency to the project
- interact with OpenCode via SDK instead of CLI
- Improve exception handling and reliability
- Support all OpenCode features programmatically

---

## Completed Features

For completed features, see [FEATURES.md](FEATURES.md).

---

## Future Enhancements

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
   - When adding a new feature, add it to the roadmap with a 🔴 status
   - When current sprint is empty, select the first 🔴 item and move it to current sprint and expand upon it with more details.
6. When committing:
   - Use `git add <specific-file>` for each changed file
   - NEVER use `git add .` or `git add -A`
   - Write clear commit messages
