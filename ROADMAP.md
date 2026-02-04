# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

### 🔴 Interactive Diff Viewer
**Priority: Medium**

Visual diff viewer within the TUI to review changes.
- View staged vs unstaged changes
- View changes from checkpoints
- Review "Dry Run" proposed changes before applying

---

## Completed Features

For completed features, see [FEATURES.md](FEATURES.md).

---

## Future Enhancements

### 🔴 Plugin Marketplace UI
**Priority: Low**

UI for browsing and managing installed plugins.

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
   - When adding a new feature, add it to the roadmap with a 🔴 status
   - When current sprint is empty, select the first 🔴 item and move it to current sprint and expand upon it with more details.
6. When committing:
   - Use `git add <specific-file>` for each changed file
   - NEVER use `git add .` or `git add -A`
   - Write clear commit messages
