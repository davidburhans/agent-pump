# Agent Pump - Roadmap

This document tracks upcoming feature development for Agent Pump. For completed features, see [FEATURES.md](FEATURES.md).

## Status Legend
- 🔴 **Not Started** - Queued for development
- 🟡 **In Progress** - Currently being worked on
- ⚫ **Deferred** - Postponed for later consideration

---

## Current Sprint

### 🔴 Enhanced Tool Security
**Priority: Medium**

Add security controls for custom tools execution.

#### Implementation Overview

- **Allow/Deny Lists**: Configure allowed commands and paths.
- **Argument Validation**: Enhanced regex and type validation for tool arguments.
- **Sandboxing**: Optional execution in isolated environments (e.g. Docker).

---

## Future Sprints

### 🔴 Context Awareness Improvements
**Priority: Medium**

Improve the context provided to agents by intelligently selecting relevant files.

#### Implementation Overview
- **Embeddings**: Use embeddings to find relevant code snippets.
- **Tree-sitter**: Parse code to understand structure and dependencies.
- **Dynamic Context**: Inject only relevant parts of large files.

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

### 🔴 Knowledge Base Integration
**Priority: Low**

Allow agents to index and search project documentation and external resources.

#### Implementation Overview
- **Indexer**: Index markdown files in `docs/` or wiki.
- **Retrieval**: RAG (Retrieval-Augmented Generation) for planning phase.
- **Context**: Inject relevant docs into context.

### 🔴 Slack Notifications
**Priority: Low**

Notify users via Slack when workflow events occur.

#### Implementation Overview
- **Event Listener**: Listen to `WorkflowCompletedEvent`, `WorkflowFailedEvent`.
- **Slack Client**: Use `slack-sdk` or simple webhook.
- **Configuration**: `webhook_config` extension or new `notification_config`.
- **Message**: Send status, link to PR (if applicable), and summary.

### 🔴 Interactive Troubleshooting
**Priority: Low**

Enable interactive chat session when a workflow fails to help diagnose issues.

#### Implementation Overview
- **Pause on Error**: Instead of stopping, transition to a "troubleshooting" state.
- **Chat Interface**: Enable a chat input in the TUI associated with the error context.
- **Context Injection**: Provide error logs and stack traces to the chat agent.
- **Resume/Retry**: Allow user to ask agent to "try again" or "apply fix" from chat.

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

### ⚫ IDE Extension
**Priority: Low**

VS Code extension to interface with Agent Pump.
- Status bar integration
- Command palette commands
- Inline chat

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
