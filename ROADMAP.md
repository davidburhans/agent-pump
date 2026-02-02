# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

*No items currently in progress. Select the next 🔴 item from Future Enhancements.*

---

## Completed Features

For completed features, see [FEATURES.md](FEATURES.md).

---

## Future Enhancements

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

### 🔴 Feature Audit
**Priority: High**

Audit the feature list FEATURES.md against the codebase for completeness and accuracy.

**Acceptance Criteria:**
- Ensure all features are fully implemented in the codebase and the user experience is smooth for interacting with them.
- Ensure all features are documented, as well as how to interact with them via the TUI, the CLI, and the Web UI.
- Ensure all features are well-tested and we do not have useless tests.
- For any feature that is not completely implemented, add it to the roadmap with a 🔴 status so it can be worked on in the future.
- For any feature that is not completely documented, add it to the roadmap with a 🔴 status so it can be worked on in the future.
- For any feature that is not completely tested, add it to the roadmap with a 🔴 status so it can be worked on in the future.
- For any feature that does not have a pleasant user experience in the TUI, CLI, or Web UI, add it to the roadmap with a 🔴 status so it can be worked on in the future.

Do this audit for all features in FEATURES.md. Update the FEATURES.md for each feature with your findings.
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
