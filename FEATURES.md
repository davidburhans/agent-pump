# Agent Pump Features

Agent Pump is a comprehensive orchestration platform designed to turn AI coding assistants into autonomous software engineers. Below is a detailed list of features and how to us them.

## 🚀 Core Workflow

The heart of Agent Pump is its recursive 5-phase workflow loop.

### 1. Planning Phase 📋
- **Description**: The agent reads your `ROADMAP.md` and generates a detailed `ENGINEERING_PLAN.md`. It breaks down high-level feature requests into actionable coding tasks.
- **Usage**: Automatically starts when a project is run. Ensure your `ROADMAP.md` has a clear "Current Sprint" section.

### 2. Implementation Phase 🔨
- **Description**: The agent executes the plan, writing code, creating files, and refactoring existing logic. It uses the `ENGINEERING_PLAN.md` as its guide.
- **Usage**: Follows the Planning phase automatically.

### 3. Verification Phase ✅
- **Description**: A two-stage verification process:
    1. **AI Verification**: The agent reviews its own code against `BEST_PRACTICES.md`.
    2. **System Verification**: Runs your configured build, lint, and test commands.
- **Usage**: Configure commands via CLI or `.agent-pump.yml`.
    ```bash
    uv run agent-pump verification set-test ./my-project "pytest"
    ```

### 4. Brainstorming Phase 💡
- **Description**: The agent reflects on the completed work and updates `ROADMAP.md` with new ideas, refactoring needs, or future tasks. You can also inject your own ideas into this phase.
- **Usage**: 
    - **Inject Idea**: Press `i` in the TUI to add an idea that the agent will consider during the next brainstorming phase.

### 5. Committing Phase 📝
- **Description**: The agent stages all changes and creates a git commit with a conventional commit message describing the work done.
- **Usage**: Automatic. Ensure your project is a git repository.

---

## 🖥️ TUI Dashboard

A powerful Terminal User Interface for managing multiple projects.

### Project Management
- **Add Project (`a`)**: Open a file dialog to add a new local project to the dashboard.
- **Remove Project (`r`)**: Remove the selected project from the dashboard (does not delete files).
- **Start/Stop (`s` / `x`)**: Start or stop the workflow for the selected project.
- **Start All / Stop All (`S` / `X`)**: Control all projects simultaneously.

### Visibility & Monitoring
- **Workflow Visualizer**: A live diagram showing exactly where the agent is in the state machine (Plan -> Implement, etc.).
- **Real-time State Indicator**: Live status showing the current phase, iteration count, and active substep/tool call.
- **Activity Log**: Real-time text stream of agent actions and output.
- **Log Filtering (`f`)**: Filter the log by specific states (e.g., only show "ERROR" or "planning") or task names.
- **Log Sorting (`o`)**: Toggle between newest-first or oldest-first log order.

---

## ⚙️ Configuration & Customization

### Flexible Backends
Configure which AI coding agent powers each phase of your workflow.

**Supported Backends:**
| Backend | CLI Tool | Notes |
|---------|----------|-------|
| **Gemini** | `gemini` | Google's AI with `--yolo` and `--checkpointing` flags |
| **Claude Code** | `claude` | Anthropic's Claude Code CLI |
| **OpenCode** | `opencode` | OpenCode CLI assistant |
| **Qwen** | `qwen` | Alibaba's Qwen CLI with `--yolo` flag |

**Configuration:**
- **Fallback Chains**: Configure a primary backend and fallback(s). If the primary fails, hits quota, or times out, the fallback takes over automatically.
- **Per-Phase Configuration**: Use a cheap/fast model for Planning and a smart/expensive model for Implementation.
- **Custom Args**: Add custom CLI arguments per-backend (e.g., `--model gemini-2.5-flash`).
- **Usage**: Press `b` in the TUI to configure backends for the selected project.

### Prompt Engineering
- **Custom System Prompts**: Inject custom instructions into the agent's context.
- **Prefix/Suffix Injection**: Add text before or after the standard system prompt.
- **Scopes**: 
    - **Global**: Applies to all projects (Press `P`).
    - **Project**: Applies to a specific project (Press `p`).

### Verification Commands
Configure exactly how the agent verifies your code.

- **Set Commands**:
  ```bash
  uv run agent-pump verification set-build <path> "<command>"
  uv run agent-pump verification set-lint <path> "<command>"
  uv run agent-pump verification set-test <path> "<command>"
  ```
- **Auto-Detection**: Attempt to auto-detect commands based on project type (Python, Node, Rust, Go).
  ```bash
  uv run agent-pump verification detect <path>
  ```

---

## 🛠️ Advanced Tools

### "Idea Queue" Injection
You can "pair program" with the agent by feeding it ideas while it works.
- **Feature**: Queue an idea (e.g., "Make sure to handle edge case X") via the TUI.
- **Result**: When the agent reaches the **Brainstorming** phase, it will read your queued ideas and incorporate them into the `ROADMAP.md` or next steps.

### Roadmap Management & Prioritization
Take control of what the agent works on next.
- **Feature**: Press `m` in the TUI to open the Roadmap Prioritization screen.
- **Usage**:
    - Select uncompleted features.
    - Reorder them using `J`/`K` or `Shift+Up`/`Shift+Down`.
    - The agent will automatically pick the new top item from the roadmap for the next Planning phase if no `TASK_NAME` is set.

### Headless CLI Mode
Run Agent Pump without the TUI, perfect for CI/CD or background workers.
- **Usage**:
  ```bash
  uv run agent-pump ./my-project --headless
  ```

### State Persistence
- **Auto-Save**: The agent saves its state after every phase. If you crash or quit, it resumes exactly where it left off.
- **Context Awareness**: It remembers completed features and failed attempts to avoid repeating mistakes.
- **Project Autoloading**: When you restart Agent Pump, it automatically loads all projects from your last active workspace.
  - **Disable Autoload**: Use the `--no-autoload` flag to start with a clean slate (projects remain on disk).
    ```bash
    uv run agent-pump --no-autoload
    ```

---

## 🔔 Notification System

Get notified when workflows complete or require attention.

- **Desktop Notifications**: Receive system notifications for major workflow events:
  - ✅ Workflow Completion (Success)
  - ❌ Workflow Failure (Error)
  - ⚠️ Verification Failure (configurable)
- **Cross-Platform**: Works on Windows, macOS, and Linux via `plyer`.
- **Configuration**: Enable/disable notifications at the workspace level.
- **Test Notifications**: Use the "Test Notification" button in TUI settings to verify setup.

---

## 📋 Copy Configuration Between Projects

Easily share backend and prompt configurations across projects.

- **Copy From**: Press `b` or `p` to open config modals, then use "Copy from..." to import settings from another project.
- **Source Selection**: Choose any existing project from a dropdown list.
- **Workspace Defaults**: Option to apply copied config to all projects as a workspace default.

---

## 📝 Per-Project Activity Logs

Each project maintains its own dedicated activity log for better organization.

- **Separate Storage**: Logs are stored per-project, not globally.
- **Contextual View**: The TUI log panel automatically switches to show logs for the selected project.
- **Global vs Project**: View all logs or filter to a specific project's activity.

---

## 🎨 Dynamic Visual State Diagrams

Interactive, animated workflow visualization with real-time state tracking.

### Features
- **Visual Workflow Nodes**: Each phase (Planning, Implementing, etc.) renders as a styled, clickable node.
- **Pulsing Active State**: The currently active node pulses to indicate activity.
- **Color-Coded States**:
  - Active: Highlighted border and pulsing animation
  - Completed: Green/success styling
  - Error: Red/error styling
- **Dynamic Configuration**: The workflow is driven by a `WorkflowDefinition` Pydantic model, allowing custom phases and transitions.

### Data-Oriented Prompt Directory
Customize prompts per-phase using markdown files:
```
.agent-pump/
├── config.yml
├── states/
│   ├── planning.md           # Full base prompt override
│   ├── pre-planning.md       # Prepended to default
│   └── post-planning.md      # Appended to default
└── backends/
    ├── pre-gemini.md         # Prepended when using Gemini
    └── post-gemini.md
```

### Migration
- Legacy `.agent-pump.yml` files can be migrated to the new directory structure via a TUI prompt.

---

## 🏗️ Architecture & Internals

### Shared Service Layer
- **Description**: A decoupled business logic layer that separates core functionality from the TUI.
- **Benefits**:
    - **UI-Agnostic**: Enables multiple interfaces (TUI, Web, CLI, IDE) to use the same logic.
    - **Stability**: Centralized state management and error handling.
    - **Services**:
        - `ProjectService`: Project lifecycle management.
        - `WorkflowService`: Workflow execution and control.
        - `IdeaService`: Idea queue management.
        - `WorkspaceService`: Configuration and workspace settings.

### Event Bus / Pub-Sub System 📢
- **Description**: A central event bus for decoupled communication between workflow execution and UI layers.
- **Benefits**:
    - **Decoupled Architecture**: Workflows publish events without knowing about subscribers.
    - **Real-time Updates**: Supports multiple subscribers (TUI widgets, WebSocket handlers) for the same event.
    - **Event Types**: Strongly typed Pydantic models for `WorkflowStateChanged`, `LogEntry`, `ProjectAdded`, etc.
    - **Async Support**: Native asyncio support with iterator-based subscription.



## 🔌 API & Architecture

### API Data Transfer Objects (DTOs)
- **Description**: Strict separation of concerns between server and clients using Pydantic DTOs.
- **Features**:
    - **Standardized Schemas**: `ProjectStatusDTO`, `WorkflowStateDTO`, `LogEntryDTO` defined in `api/schemas.py`.
    - **CamelCase Serialization**: Optimized for web clients and OpenAPI consumption.
    - **Factory Methods**: Robust `from_internal()` converters to safe-guard internal models.
