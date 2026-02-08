# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).

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

## Future Sprints

### 🔴 Smart Reviewer Assignment
**Priority: Medium**

Automatically assign reviewers to PRs based on project context:
- Parse CODEOWNERS file.
- Analyze git history for frequent contributors to modified files.
- Assign reviewers via GitHub API during PR creation.
- Load balance reviews across team members (if configured).

---

### 🔴 Smart Feature Prioritization
**Priority: Medium**

Enhance roadmap management with intelligent prioritization:
- Analyze dependency relationships between features
- Suggest optimal execution order based on project structure
- Auto-reorder roadmap items to minimize rework
- Visualize feature dependencies in workflow editor

---

### 🔴 Multi-Project Orchestration
**Priority: Medium**

Coordinate work across multiple projects simultaneously:
- Execute workflows for multiple projects in parallel
- Share context between related projects (e.g., shared libraries)
- Priority-based scheduling for project execution queues
- Cross-project dependency tracking

---

### 🔴 PR Status Monitoring & Updates
**Priority: Medium**

Monitor and update PR status throughout development:
- Watch PR status changes (approved, changes requested, failed checks)
- Auto-resolve merge conflicts when possible
- Update PR description with implementation progress
- Notify on critical PR events

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
