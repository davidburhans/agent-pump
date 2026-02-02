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
- **Usage**: Configure commands via CLI or `.agent-pump/config.yml`.
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

## 🧠 Smart Context Window Management

Intelligently manage what context is sent to AI agents to maximize effectiveness within token limits. Automatically prioritizes relevant files, summarizes large files, and tracks recently modified files.

### Features
- **Project Analysis**: Analyzes project size and provides statistics on token usage
- **File Prioritization**: Scores files by relevance (source > tests, recent > old, small > large)
- **Automatic Summarization**: Summarizes large files that exceed configurable thresholds
- **Recently Modified Tracking**: Boosts priority for files the agent has recently touched
- **Manual Overrides**: Allows explicit inclusion/exclusion of specific files
- **Token Budgeting**: Respects context window limits per backend (Gemini: 1M-2M, Claude: 200K, etc.)
- **Extension Filtering**: Configurable file extensions to include (defaults to common code files)
- **Pattern Exclusion**: Glob patterns to exclude directories like `.git`, `node_modules`, etc.

### Configuration

Configure context management in your `.agent-pump/config.yml`:

```yaml
context:
  # Token limits
  max_context_tokens: 100000      # Maximum tokens to send (default: 100K)
  reserve_tokens: 10000           # Reserve for AI response (default: 10K)
  
  # File filtering
  include_extensions:             # File types to include
    - ".py"
    - ".js"
    - ".md"
  exclude_patterns:               # Glob patterns to exclude
    - ".git"
    - "node_modules"
    - "__pycache__"
  
  # Prioritization
  prioritize_recently_modified: true    # Boost recently modified files (default: true)
  recently_modified_boost: 2.0          # Score multiplier (default: 2.0)
  
  # Large file handling
  large_file_threshold: 50000     # Characters (default: 50K)
  summarize_large_files: true     # Auto-summarize large files (default: true)
  max_summary_length: 1000        # Max chars in summary (default: 1K)
```

### Usage

Context management is automatic once configured. The system will:
1. Analyze your project before each phase
2. Select the most relevant files within your token budget
3. Summarize large files to preserve context space
4. Track which files the agent modifies for future prioritization

You can also manually track modifications:
```python
from agent_pump.utils.context_manager import ContextManager

manager = ContextManager(project_path)
manager.track_file_modification("src/main.py")
```

### Token Counting

Token counts are estimated differently per backend:
- **Gemini**: ~3.8 chars per token
- **Claude**: Uses tiktoken (cl100k_base) if available, otherwise ~3.5 chars per token
- **Qwen**: Uses tiktoken if available, otherwise ~4 chars per token
- **OpenCode**: ~4 chars per token

Context window sizes:
- **Gemini Flash**: 1M tokens
- **Gemini Pro**: 2M tokens
- **Claude**: 200K tokens
- **Qwen**: 128K tokens
- **OpenCode**: 128K tokens

---

## 💰 Cost Tracking & Budgets

Track API costs and set spending limits per project or workspace-wide to control AI backend expenses.

### Overview

Automatic cost tracking for API usage across all backend invocations. The system records token usage and calculates costs using real backend pricing, providing detailed breakdowns and budget enforcement.

### Features

- **Automatic Token Counting**: Per-phase token usage tracking for every backend invocation
- **Cost Calculation**: Uses real backend pricing rates for accurate cost estimation
- **Per-Project Aggregation**: Track costs individually for each project
- **Workspace-Wide Aggregation**: View total costs across all projects in a workspace
- **Cost Breakdowns**: Analyze costs by phase (planning, implementing, verifying, etc.) and by backend (Gemini, Claude, Qwen, OpenCode)
- **Budget Limits**: Set daily, weekly, and monthly spending limits
- **Budget Enforcement**: Configurable actions when budgets are exceeded:
  - `pause`: Stop workflow execution (can be manually resumed)
  - `warn`: Log a warning but continue execution
  - `ignore`: Silently continue without notification
- **Cost Export**: Export cost data as JSON or CSV for external analysis

### CLI Commands

View and manage costs via the command line:

```bash
# View costs for current workspace
uv run agent-pump cost show

# View costs for specific project
uv run agent-pump cost show ./my-project

# View costs for specific time period
uv run agent-pump cost show --period daily
uv run agent-pump cost show --period weekly
uv run agent-pump cost show --period monthly

# Export costs as JSON
uv run agent-pump cost export --format json --output costs.json

# Export costs as CSV
uv run agent-pump cost export --format csv --output costs.csv

# Reset costs for a project
uv run agent-pump cost reset ./my-project

# View cost breakdown by phase
uv run agent-pump cost breakdown --by phase

# View cost breakdown by backend
uv run agent-pump cost breakdown --by backend

# View current budget status
uv run agent-pump budget show

# Set daily budget limit
uv run agent-pump budget set --daily 5.00

# Set weekly budget limit
uv run agent-pump budget set --weekly 25.00

# Set monthly budget limit
uv run agent-pump budget set --monthly 100.00

# Enable budget enforcement
uv run agent-pump budget enable

# Disable budget enforcement
uv run agent-pump budget disable
```

### Backend Pricing

Backend pricing rates (per 1K tokens):

| Backend | Input | Output |
|---------|-------|--------|
| Gemini Flash | $0.000125 | $0.000375 |
| Gemini Pro | $0.00035 | $0.00105 |
| Claude 3.5 Sonnet | $0.003 | $0.015 |
| Qwen | $0.0005 | $0.001 |
| OpenCode | $0 (local) | $0 (local) |

### Configuration

Budgets are configured per-workspace and stored alongside cost data. Configure via `.agent-pump/config.yml`:

```yaml
budget_config:
  enabled: true                    # Enable budget tracking
  daily_limit: 5.0                # Daily budget in USD
  weekly_limit: 25.0              # Weekly budget in USD
  monthly_limit: 100.0            # Monthly budget in USD
  action_on_exceeded: "pause"     # Action: pause, warn, or ignore
```

Budget and cost data is stored per-workspace at:
- **Location**: `~/.config/agent-pump/costs/{workspace_name}.json`
- **Format**: JSON with records array and budget configuration
- **Auto-save**: Costs are saved automatically after each backend invocation

---

## 🌿 Git Branch Strategy

Smart branch management for feature development to avoid cluttering the main branch with work-in-progress commits.

### Features
- **Automatic Feature Branch Creation**: Before the planning phase, automatically create a feature branch with a standardized naming convention
- **Branch Naming Convention**: Branches are named automatically from the feature title (e.g., `feature/add-login-page`)
- **Auto-merge**: Optionally merge the feature branch back to the base branch after successful verification
- **Merge Conflict Handling**: Gracefully detects and handles merge conflicts by pausing the workflow for manual resolution

### Configuration

Enable branch strategy in your `.agent-pump/config.yml`:

```yaml
branch_strategy:
  enabled: true                    # Enable branch strategy (default: false)
  auto_create_branch: true         # Create feature branch before planning
  auto_merge: false               # Auto-merge after verification (use with caution)
  branch_prefix: "feature"        # Prefix for feature branches
  base_branch: "main"             # Base branch to create from
  require_clean_worktree: true    # Require clean git status
  push_on_merge: false            # Push to remote after merge
```

### Workflow Integration

When enabled, the branch strategy automatically:
1. Creates a feature branch before the planning phase (e.g., `feature/my-feature-name`)
2. Works on the feature branch throughout all workflow phases
3. If `auto_merge` is enabled, attempts to merge after the committing phase
4. On merge conflicts, pauses the workflow and notifies you to resolve manually

---

## 🖥️ TUI Dashboard

A powerful Terminal User Interface for managing multiple projects.

### Project Management
- **Add Project (`a`)**: Open a file dialog to add a new local project to the dashboard.
- **Remove Project (`delete`)**: Remove the selected project from the dashboard (does not delete files).
- **Start/Stop (`s` / `x`)**: Start or stop the workflow for the selected project.
- **Start All / Stop All (`S` / `X`)**: Control all projects simultaneously.

### Multi-Workspace Management
Manage multiple isolated workspaces with different project sets and configurations.

- **CLI Commands**: Full workspace management via CLI:
  ```bash
  uv run agent-pump workspace list          # List all workspaces
  uv run agent-pump workspace create <name> # Create new workspace
  uv run agent-pump workspace switch <name> # Switch to workspace
  uv run agent-pump workspace delete <name> # Delete workspace
  uv run agent-pump workspace show          # Show current workspace details
  ```
- **TUI Workspace Switcher**: Press `W` in the TUI to open the workspace switcher modal
- **Isolated Project Lists**: Each workspace maintains its own independent project list
- **Workspace-Specific Settings**: Each workspace has its own:
  - Backend configuration defaults
  - Global prompt settings
  - Idea queue
  - Project-specific configurations

### Custom Workflow Editor
Design and customize your own workflow state machines beyond the default 5-phase workflow.

- **Interactive Editor**: Press `e` in the TUI to open the workflow editor
- **Visual Phase Management**: Add, edit, and reorder workflow phases with a graphical interface
- **Per-Phase Configuration**: Configure each phase with:
  - Name, description, and icon
  - Success and failure transition targets
  - Timeout settings (override global default)
  - Retry behavior (max retries, retry delay)
- **Transition Visualization**: See all workflow transitions in the Transitions tab
- **Template System**: Start from built-in templates (minimal, default, extended)
- **Import/Export**: Save workflows as YAML or JSON for sharing and version control
- **Validation**: Built-in validation ensures workflow integrity before saving
- **Project Association**: Assign custom workflows to specific projects

**Usage:**
```bash
# Open workflow editor from TUI (press 'e' when a project is selected)
# Or use the command palette (Ctrl+P) and search for "Edit Workflow"
```

### Visibility & Monitoring
- **Workflow Visualizer**: A live diagram showing exactly where the agent is in the state machine (Plan -> Implement, etc.).
- **Real-time State Indicator**: Live status showing the current phase, iteration count, and active substep/tool call.
- **Activity Log**: Real-time text stream of agent actions and output.
- **Log Filtering (`f`)**: Filter the log by specific states (e.g., only show "ERROR" or "planning") or task names.
- **Log Sorting (`o`)**: Toggle between newest-first or oldest-first log order.

### Command Palette
- **Access**: Press `Ctrl+P` to open the command palette.
- **Features**: Fuzzy search for any command, even those not bound to a key.
- **Context Aware**: Shows project-specific commands only when a project is selected.

### UX & Theming
- **Semantic Colors**: The TUI uses a consistent semantic color scheme (Primary, Secondary, Success, Error, Warning) defined in TCSS variables.
- **Themes**: Built-in support for Dark (default) and Light themes.
- **Visual Feedback**: Consistent use of color to indicate status (e.g., Green for success/completed, Red for error).
- **Form Validation**: Real-time validation with visual feedback (shake animation, error labels) powered by Pydantic models for data integrity.
- **Accessibility**: Enhanced screen reader support with `accessible_name` on custom widgets, improved color contrast, and keyboard navigation support (tooltips, tab flow).
- **Focus Indicators**: Distinct "glowing" border styles for focused elements (Buttons, Inputs, Cards) to improve keyboard navigation visibility.
- **Rich Content**: Enhanced log display using Tables for data, Panels for phase transitions/errors, and Syntax highlighting, replacing basic text output.

---

## ⚙️ Configuration & Customization

### Project Configuration Structure

Agent Pump stores all project-specific configuration in the `.agent-pump/` directory:

```
.agent-pump/
├── config.yml              # Main configuration file
├── workflow.yaml           # Workflow state machine definition
├── states/                 # Custom prompt files
│   ├── planning.md
│   ├── implementing.md
│   ├── verifying.md
│   ├── brainstorming.md
│   └── committing.md
└── backends/               # Backend-specific prompts
    ├── pre-gemini.md
    └── post-gemini.md
```

**Note**: The legacy `.agent-pump.yml` file format is no longer supported. All configuration must use the `.agent-pump/config.yml` path.

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

### Single Backend Instance Enforcer
Enables strict rate limit control for shared resources (e.g., Free Tier API accounts or single-instance CLIs).

- **Turn-Taking**: Ensures only one workflow runs on a specific backend configuration at a time across all projects.
- **Configurable**: Set `concurrency_limit` per backend in your workspace config. Default is `1` (serial execution). To enable parallel execution, set to `0`.
- **Global**: Works across all loaded projects in the current workspace.

### Prompt Engineering
- **Custom System Prompts**: Inject custom instructions into the agent's context.
- **Prefix/Suffix Injection**: Add text before or after the standard system prompt.
- **Scopes**: 
    - **Global**: Applies to all projects (Press `P`).
    - **Project**: Applies to a specific project (Press `p`).

### Keybindings Manifest ⌨️
- **Description**: Centralized configuration for all keyboard shortcuts.
- **Capabilities**:
    - **Single Source of Truth**: All keybindings defined in `src/agent_pump/keybindings.py`.
    - **Shared Definitions**: Ensures consistency between TUI and future Web Dashboard.
    - **Metadata**: Each binding includes description and scope (Global vs Project) for better help displays.

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

### Dry Run Mode 🎭
Preview what the agent would do without making actual changes. Perfect for testing configurations, estimating costs, and reviewing planned actions before committing.

#### Features
- **No Changes Made**: All file system operations, git commands, and backend invocations are intercepted and logged but not executed
- **Comprehensive Reporting**: Generates detailed reports showing:
  - Files that would be created, modified, or deleted
  - Git operations (branch creation, commits, merges)
  - Backend invocations with token estimates
  - Cost estimates per phase and total
- **Token & Cost Estimation**: Estimates token usage and API costs based on prompt length and backend rates
- **CLI Integration**: Use `--dry-run` flag with headless mode
- **Visual Indicator**: TUI shows [DRY RUN] indicator when enabled

#### Usage

**Headless Mode:**
```bash
# Preview what the agent would do
uv run agent-pump ./my-project --no-tui --dry-run

# With max iterations limit
uv run agent-pump ./my-project --no-tui --dry-run --max-iterations 3
```

**TUI Mode:**
```bash
# Launch TUI in dry-run mode
uv run agent-pump ./my-project --dry-run
```

**Bootstrap with Dry Run:**
```bash
# Preview what would be generated
uv run agent-pump project bootstrap ./my-project --dry-run
```

#### Report Output
When running in dry-run mode, a comprehensive report is displayed showing:

```
============================================================
DRY RUN REPORT
============================================================
Project: my-project
Duration: 45.23s
Status: ✓ Would Succeed

----------------------------------------
FILE CHANGES
----------------------------------------
  Created: 3 files
  Modified: 1 files
  Deleted: 0 files

----------------------------------------
GIT OPERATIONS
----------------------------------------
  • Create branch: feature/add-login-page
  • Commit changes: feat: add user authentication

----------------------------------------
BACKEND INVOCATIONS
----------------------------------------
  Total: 5 invocations
  • gemini: planning
  • gemini: implementing
  • gemini: verifying

----------------------------------------
COST ESTIMATES
----------------------------------------
  Total Tokens: 15,000
    - Input: 10,000
    - Output: 5,000
  Estimated Cost: $0.0450 USD

----------------------------------------
PHASE BREAKDOWN
----------------------------------------
  planning: 3,000 tokens ($0.0090)
  implementing: 8,000 tokens ($0.0240)
  verifying: 4,000 tokens ($0.0120)

============================================================
```

#### Cost Estimation
Supported backends with approximate rates:
- **Gemini 1.5 Flash**: $0.000125/1K input, $0.000375/1K output
- **Claude 3.5 Sonnet**: $0.003/1K input, $0.015/1K output
- **Qwen**: $0.0005/1K input, $0.001/1K output
- **OpenCode**: Local model (no cost)

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

### Dynamic Visual State Diagrams

Interactive, animated workflow visualization with real-time state tracking.

#### Features
- **Visual Workflow Nodes**: Each phase (Planning, Implementing, etc.) renders as a styled, clickable node.
- **Deep-Linking Configuration**: Clicking a phase node automatically opens the Prompt Configuration modal to that specific phase's tab, allowing for rapid iteration on prompts.
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

### Configuration Structure
Agent Pump uses the `.agent-pump/` directory structure for all project configuration. The legacy `.agent-pump.yml` file format is no longer supported. Use `.agent-pump/config.yml` instead.

---

## 🔍 Performance Audit & Debuggability

Comprehensive debugging, monitoring, and observability features for diagnosing issues in long-running sessions.

### Subprocess Lifecycle Management
- **Tracking**: Monitors all active subprocesses with PID, command, project, and timing info
- **Cleanup**: Ensures proper process termination on cancellation or timeout
- **Metrics**: Tracks spawned, completed, timed-out, and cancelled processes
- **Zombie Detection**: Identifies orphaned processes for cleanup
- **API**: Access via `agent_pump.utils.subprocess_manager`

### Memory Profiling
- **Real-time Snapshots**: Captures RSS, VMS, and percentage memory usage
- **Leak Detection**: Algorithmic detection of memory growth patterns over time
- **Peak Tracking**: Monitors peak memory usage across session
- **Graceful Degradation**: Works without `psutil` (optional dependency)
- **CLI**: Check memory via `agent-pump health` command

### Structured Logging
- **Multiple Levels**: DEBUG, INFO, WARNING, ERROR with configurable verbosity
- **JSON Format**: Machine-parseable structured logs for external analysis
- **Colorized Console**: Human-readable colored output for terminal use
- **File Output**: Optional file-based logging with different format
- **Runtime Changes**: Adjust log levels without restart
- **CLI Flag**: Use `--debug` for instant verbose logging

### Health Check & Monitoring
- **Extended Endpoint**: `GET /health` now includes comprehensive metrics
  - Memory usage (RSS, VMS, percentage)
  - Subprocess statistics (active, spawned, completed, timeouts)
  - Event queue depth
  - Server uptime
- **CLI Command**: `agent-pump health` displays current resource usage
- **Pattern Analysis**: Timeout tracking identifies hanging operations

### Timeout Instrumentation
- **Operation Tracking**: Monitors timeouts across backend execution and verification
- **Pattern Detection**: Identifies which operations timeout most frequently
- **Context Preservation**: Captures project, phase, and duration information
- **API**: Access via `agent_pump.utils.timeout_tracker`

### Debug Mode
- **CLI Flag**: `--debug` enables verbose diagnostics without config changes
- **Automatic**: Sets log level to DEBUG and enables additional diagnostics
- **Convenient**: No need to modify `.agent-pump/config.yml`

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

### Log Streaming Service
- **Description**: A unified service for managing log storage and streaming across the platform.
- **Capabilities**:
    - **Buffered Storage**: In-memory circular buffer for recent log history.
    - **Streaming API**: Async iterator support for real-time log streaming to web clients.
    - **Multi-Tenant**: Manages separate log buffers for each project.

## 🔌 API & Architecture

### API Data Transfer Objects (DTOs)
- **Description**: Strict separation of concerns between server and clients using Pydantic DTOs.
- **Features**:
    - **Standardized Schemas**: `ProjectStatusDTO`, `WorkflowStateDTO`, `LogEntryDTO` defined in `api/schemas.py`.
    - **CamelCase Serialization**: Optimized for web clients and OpenAPI consumption.
    - **Factory Methods**: Robust `from_internal()` converters to safe-guard internal models.

### HTTP Server Infrastructure 🌐
- **Description**: A foundational FastAPI-based web server enabling remote monitoring and future dashboard capabilities.
- **Capabilities**:
    - **FastAPI Backend**: High-performance, async-native REST API.
    - **WebSocket Support**: Real-time bidirectional communication at `/ws` for live updates.
    - **CORS & Auth**: Configurable Middleware for secure cross-origin resource sharing and authentication.
    - **CLI Integration**: Run with `agent-pump --web` to start the server (standalone or alongside TUI).
    - **Endpoints**:
        - `GET /health`: System health status.
        - `GET /docs`: Interactive Swagger UI documentation.

### Web Dashboard UI 🖥️
- **Description**: A modern, responsive web interface for managing Agent Pump.
- **Capabilities**:
    - **Single Page App**: React-based UI served directly by the backend.
    - **Real-time Updates**: Live log streaming and workflow visualization via WebSocket.
    - **TUI Mirror**: Replicates key TUI features (Project List, Activity Log, Workflow Graph) in the browser.
    - **Dark Mode**: Default dark theme matching the terminal aesthetic.
    - **Access**: Available at `http://localhost:8000` when running with `--web`.

## 📊 Metrics & Analytics Dashboard

Track productivity metrics across projects and time periods to understand your development patterns.

### Capabilities
- **Feature Tracking**: Count completed features per day, week, or month
- **Phase Timing**: Track time spent in each workflow phase (planning, implementing, verifying, etc.)
- **Success Metrics**: Monitor success/failure rates for verification and feature completion
- **Export Data**: Export metrics as JSON or CSV for external analysis

### Access Methods

#### TUI Dashboard
Press `M` in the TUI to open the metrics dashboard modal:
- Summary view with key statistics
- Features list with completion details
- Phase timing breakdown
- One-click export buttons

#### CLI Commands
```bash
# Display metrics summary
uv run agent-pump metrics show

# Export metrics to file
uv run agent-pump metrics export --format json --output metrics.json

# Clear metrics data
uv run agent-pump metrics clear
```

#### API Endpoints
When running with `--web`:
- `GET /api/metrics` - Overall workspace metrics
- `GET /api/metrics/summary?period=day|week|month` - Summary by time period
- `GET /api/metrics/projects/{path}` - Per-project metrics
- `GET /api/metrics/export/json` - Export as JSON
- `GET /api/metrics/export/csv` - Export as CSV

### Data Storage
Metrics are stored separately from project state at:
- Location: `~/.config/agent-pump/metrics_{workspace}.json`
- Format: JSON with version tracking
- Per-workspace: Each workspace has its own metrics file

---

## 🏗️ Project Templates

Quickly bootstrap new projects with pre-configured settings including backend configuration, custom prompts, and verification commands.

### Features
- **Save Project as Template**: Save any project's configuration as a reusable template
- **Built-in Templates**: Pre-configured templates for common tech stacks:
  - **Python/uv**: Python project with uv toolchain, ruff linting, and pytest
  - **Node/npm**: Node.js project with npm, eslint, and jest
  - **Rust/cargo**: Rust project with cargo and clippy
  - **Go**: Go project with standard tooling and golangci-lint
- **Template Application**: Apply templates to existing projects or create new projects from templates
- **User Templates**: Create and manage custom templates for your specific needs
- **Full Configuration**: Templates include:
  - Backend selection and phase-specific backend chains
  - Workflow settings (max iterations, timeout)
  - Branch strategy configuration
  - Verification commands (build, lint, test)
  - Custom prompts for all workflow phases
  - Backend-specific prompt hooks

### CLI Commands

```bash
# List all available templates (built-in + user)
uv run agent-pump template list

# Save current project as a template
uv run agent-pump template save ./my-project my-template --description "My custom template"

# Show template details
uv run agent-pump template show python-uv

# Apply a template to an existing project
uv run agent-pump template apply python-uv ./existing-project

# Create a new project from a template
uv run agent-pump template apply python-uv ./new-project --create

# Delete a user-created template
uv run agent-pump template delete my-template
```

### Template Storage
Templates are stored in `~/.config/agent-pump/templates/` as JSON files. User templates override built-in templates with the same name.

---

## 🚀 Project Bootstrap

Quickly bootstrap existing projects with AI-generated `ROADMAP.md` and `BEST_PRACTICES.md` files, allowing you to start using Agent Pump on any project immediately.

### Features
- **Automatic Project Analysis**: Detects project type (Python, Node.js, Rust, Go, Java), framework, and structure
- **AI-Powered Generation**: Uses your configured AI backend (Gemini, Claude, Qwen, OpenCode) to generate appropriate documentation
- **Smart Detection**: Recognizes:
  - Python projects (uv, Poetry, pip)
  - Node.js projects (React, Vue, Angular, Next.js, Express)
  - Rust projects (Cargo)
  - Go projects (Go modules)
  - Java projects (Maven, Gradle)
- **Test Infrastructure Detection**: Identifies test directories and configuration files
- **CI/CD Detection**: Recognizes GitHub Actions, GitLab CI, and other CI configurations

### CLI Commands

```bash
# Bootstrap a project with default Gemini backend
uv run agent-pump project bootstrap ./my-project

# Bootstrap with a specific backend
uv run agent-pump project bootstrap ./my-project --backend claude

# Preview what would be generated (dry run)
uv run agent-pump project bootstrap ./my-project --dry-run
```

### What Gets Generated

**ROADMAP.md** includes:
- Status legend for tracking progress
- Current Sprint section with 2-3 realistic initial tasks
- Future Enhancements section with potential features
- Properly formatted for Agent Pump to use

**BEST_PRACTICES.md** includes:
- Code style guidelines specific to your language
- Testing requirements
- Documentation standards
- Git practices and commit conventions
- Verification checklist

### Workflow

1. Run the bootstrap command on an existing project
2. Agent Pump analyzes the project structure
3. AI backend generates appropriate documentation
4. Files are created in the project root
5. Project is ready to use with Agent Pump immediately

---

## 🔄 Checkpoint Rollback System

Save and restore project states at any point in the workflow. Checkpoints provide safety nets for experimentation and the ability to undo changes.

### Features

- **Automatic Checkpoints**: Created automatically before each workflow phase (planning, implementing, verifying, brainstorming, committing)
- **Manual Checkpoints**: Create manual save points at any time with custom descriptions
- **Checkpoint List**: View all checkpoints with timestamps, phase information, and descriptions
- **One-Click Rollback**: Restore project to any previous checkpoint via git reset
- **Backup Branches**: Automatic backup branch creation before rollback for additional safety
- **File Tracking**: Checkpoints track which files were modified since the last checkpoint

### TUI Keybindings

| Key | Action | Description |
|-----|--------|-------------|
| `c` | Create Checkpoint | Create a manual checkpoint for the selected project |
| `C` | Show Checkpoints | Open checkpoint list modal to view and rollback |

### Checkpoint Modal

Press `C` to open the checkpoint management modal:

- **List View**: See all checkpoints with ID, timestamp, phase, type (Auto/Manual), commit hash, and description
- **Details Panel**: Click any checkpoint to see full details including files modified
- **Rollback Button**: One-click rollback to selected checkpoint with automatic backup
- **Keyboard Navigation**: Use `r` key to rollback selected checkpoint, `Escape` to close

### How Checkpoints Work

1. **Creation**: Checkpoints are implemented as git commits with a special `[checkpoint]` prefix in the commit message
2. **Storage**: Checkpoint metadata (ID, timestamp, description, files modified) is stored in `.agent-pump/state.json`
3. **Rollback**: Uses `git reset --hard` to restore to the checkpoint commit
4. **Safety**: Creates a backup branch (`backup/{branch}/before-rollback-{id}`) before rolling back
5. **Limit**: Maximum of 50 checkpoints are kept per project (oldest are trimmed automatically)

### Workflow Integration

- **Auto-Checkpoint**: Before each phase starts, an automatic checkpoint is created
- **Phase Tracking**: Each checkpoint records which workflow phase it was created in
- **Feature Association**: Checkpoints track the current feature being worked on
- **Post-Rollback**: After rollback, the workflow is automatically reset to idle state

---

## 🚀 Parallel Project Execution Limits

Control resource usage when running multiple projects simultaneously with a priority-based queue system and configurable concurrency limits.

### Features

- **Configurable Concurrency Limits**: Set maximum concurrent project executions (default: 3, 0 = unlimited)
- **Priority-Based Queue**: Projects queue when limit is reached with High/Medium/Low priority levels
- **Automatic Queue Management**: Projects automatically start when slots become available
- **Queue Persistence**: Queue state persists across application restarts via workspace configuration
- **Comprehensive Testing**: Full test coverage with unit and integration tests

### Configuration

Execution queue settings are stored in workspace configuration:

```python
# In your workspace configuration (managed automatically)
execution_queue_config:
  max_concurrent: 3        # Maximum concurrent executions (0 = unlimited)
  auto_start_queued: true  # Auto-start queued projects when slots available
```

### Queue Priority Levels

- **HIGH (3)**: Urgent projects - jumps ahead of medium/low priority
- **MEDIUM (2)**: Default priority for most projects
- **LOW (1)**: Background projects - yields to higher priorities

### Programmatic API

```python
from agent_pump.models.execution_queue import QueuePriority
from agent_pump.services.execution_queue_service import ExecutionQueueService

# Enqueue a project with high priority
success, message = await execution_queue_service.enqueue_project(
    workspace, path, priority=QueuePriority.HIGH
)

# Get queue status
status = execution_queue_service.get_queue_status(workspace)

# Get specific project queue info
info = execution_queue_service.get_project_queue_info(workspace, path)
```

### Queue States

Projects in the queue can have the following states:
- **QUEUED**: Waiting in queue for a slot
- **ACTIVE**: Currently executing
- **COMPLETED**: Finished successfully
- **FAILED**: Encountered an error
- **CANCELLED**: Manually cancelled

### Event Integration

The execution queue publishes events via the EventBus:
- `ProjectQueuedEvent`: When a project is added to queue
- `ProjectDequeuedEvent`: When a project is removed from queue
- `QueuePositionChangedEvent`: When queue order changes
- `ProjectStartedFromQueueEvent`: When a queued project starts

### Testing

The execution queue includes comprehensive test coverage:

```bash
# Run execution queue tests
uv run pytest tests/unit/models/test_execution_queue.py -v
uv run pytest tests/unit/services/test_execution_queue_service.py -v
uv run pytest tests/integration/test_execution_queue_integration.py -v
```

**Test Coverage:**
- Queue priority ordering (67 tests)
- Concurrency limit enforcement
- Auto-start behavior
- Priority updates
- Queue status reporting
- Failure handling
- Cleanup operations
- End-to-end workflow integration

---

## 🚦 Approval Gates

Require human approval at configurable points in the workflow before proceeding. This safety feature allows you to review changes before critical phases like committing.

### Features

- **Phase-Based Gates**: Configure approval requirements for any workflow phase
- **Desktop Notifications**: Receive system notifications when approval is needed
- **Timeout Behavior**: Auto-approve, auto-reject, or wait indefinitely on timeout
- **Batch Approval**: Approve or reject multiple pending requests at once
- **Approval Comments**: Add optional comments when approving or rejecting
- **Persistent State**: Pending approvals survive application restarts

### Configuration

Enable approval gates in your `.agent-pump/config.yml`:

```yaml
approval_gate:
  enabled: true
  gates:
    - phase: committing
      timeout_minutes: 30
      timeout_action: auto_reject  # or auto_approve, wait
      require_comment: false
  notifications:
    desktop: true
    timeout_warning_minutes: 5
```

### Usage

When a gated phase is reached:
1. Workflow pauses automatically
2. Desktop notification is sent (if enabled)
3. Approval modal appears in TUI with project details
4. Review the changes, then approve or reject
5. Workflow continues based on decision

### Timeout Actions

Configure what happens when approval times out:
- **WAIT**: Keep waiting indefinitely for manual approval
- **AUTO_APPROVE**: Automatically approve and continue workflow
- **AUTO_REJECT**: Reject approval and halt workflow (default)

### Programmatic API

```python
from agent_pump.models.approval_gate_config import ApprovalGateConfig, GateConfig
from agent_pump.services.approval_gate_service import ApprovalGateService

# Configure approval gates for a project
config = ApprovalGateConfig(
    enabled=True,
    gates=[
        GateConfig(
            phase="committing",
            timeout_minutes=30,
            require_comment=True,
        )
    ]
)

# Request approval (returns None if phase not gated)
request = await approval_service.request_approval(
    project_path=Path("./my-project"),
    phase="committing",
    feature="Add login page",
    config=config,
)

# Wait for approval decision
result = await approval_service.wait_for_approval(request.id)
# Returns: True (approved), False (rejected), or None (timeout/error)

# Batch approve all pending requests
count = await approval_service.batch_approve_all(comment="Bulk approval")
```

### Testing

```bash
# Run approval gate tests
uv run pytest tests/unit/models/test_approval_gate_config.py -v
uv run pytest tests/unit/services/test_approval_gate_service.py -v
uv run pytest tests/unit/tui/test_approval_gate_modal.py -v
```

**Test Coverage:**
- Configuration model validation
- Approval request lifecycle
- Timeout handling
- Batch operations
- Event publishing
- State persistence
