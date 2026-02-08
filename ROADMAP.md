# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

### 🔴 Code Context Visualizer
**Priority: Low**

Visualize the retrieved context chunks in the TUI to debug the RAG system.

#### Implementation Overview
- **UI Panel**: Add a new tab or panel in the TUI to show `retrieved_context`.
- **Search Interface**: Allow users to manually query the vector store to test retrieval.
- **Debugging**: Show similarity scores and file sources.

### 🔴 External Documentation Crawler
**Priority: Low**

Allow agent to crawl external documentation URLs and add them to context.

#### Implementation Overview
- **MCP Tool**: Create a built-in MCP tool `crawl_documentation(url)`.
- **Scraper**: Use `beautifulsoup4` or similar to extract text from documentation pages.
- **Context Injection**: Add crawled content to vector store or transient context.
- **Caching**: Cache crawled pages to prevent redundant requests.

---

## Deferred Features

### 🔴 Self-Healing Verification
**Priority: Low**

When verification fails, attempt to automatically fix the code.

#### Implementation Overview
- **New Phase**: Add `repairing` phase.
- **Workflow Update**: Change `verifying` failure transition to `repairing`.
- **Repair Loop**: `repairing` -> `verifying`.
- **Retry Limit**: Enforce max retries to prevent infinite loops.

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

### ⚫ IDE Extension
**Priority: Low**

VS Code extension to interface with Agent Pump.
- Status bar integration
- Command palette commands
- Inline chat

---

### 🔴 Workflow Analytics Dashboard
**Priority: Low**

Visualize workflow performance metrics and costs over time.

#### Implementation Overview
- **Data Collection**: Aggregate metrics from `CostTrackingService` and `WorkflowState`.
- **TUI Dashboard**: Add a new screen in TUI to show graphs (using textual-plotext or similar).
- **Metrics**: Success rate, average phase duration, token usage, cost per feature.

### 🔴 Enhanced Troubleshooting with Auto-Fix
**Priority: Low**

Automatically suggest and apply fixes during troubleshooting mode.

#### Implementation Overview
- **Auto-Fix Analysis**: When in troubleshooting mode, automatically run an "analysis" agent to suggest fixes.
- **One-Click Fix**: Add "Apply Fix" button in the chat interface.
- **Diff Preview**: Show diff of proposed fix before applying.

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

### 🔴 Workflow Templates
**Priority: Low**

Allow users to define custom workflow states and transitions in configurable templates.

#### Implementation Overview
- **Template Schema**: Define a YAML/JSON schema for workflow definitions.
- **Template Loader**: Load templates from `.agent-pump/templates/` or global config.
- **Project Selection**: Allow selecting a workflow template when initializing a project.

### 🔴 Configurable Backend Parameters
**Priority: Low**

Allow fine-tuning of backend parameters (temperature, top_p, max_tokens) via configuration.

#### Implementation Overview
- **Configuration**: Extend `Config` model to support `backend_options` dict.
- **Backend Interface**: Update `AgentBackend.run` to accept options.
- **Implementation**: Pass options to LLM API calls.
