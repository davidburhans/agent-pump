# Agent Pump ⛽

Agent Pump is a terminal-based orchestration platform that turns AI coding assistants into autonomous agents. It manages the entire software engineering lifecycle through a rigorous, state-driven workflow loop.

## Project Overview

Agent Pump implements a state machine that models the software engineering process:
**Plan → Implement → Verify → Brainstorm → Commit**

- **Plan**: Analyzes the codebase and `ROADMAP.md` to create an implementation plan.
- **Implement**: Writes code following the plan using pluggable LLM backends.
- **Verify**: Runs tests, linters, and builds; automatically loops back to implementation on failure.
- **Brainstorm**: Reviews completed work and updates the project roadmap or handles idea queues.
- **Commit**: Stages and commits changes with conventional commit messages.

### Core Technologies
- **Language**: Python 3.12+
- **Task Orchestration**: `transitions` (state machine logic)
- **TUI Framework**: `Textual`
- **CLI Framework**: `Click`
- **API Framework**: `FastAPI` & `Uvicorn`
- **Models/Validation**: `Pydantic`
- **Git Integration**: `GitPython`
- **Package Management**: `uv`

## Building and Running

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)

### Setup
```bash
# Install dependencies
uv sync
```

### Running the Application
```bash
# Launch the TUI (main interface)
uv run agent-pump

# Launch the Web Server
uv run agent-pump --web --web-port 8000

# Headless mode for CI/CD
uv run agent-pump ./my-project --no-tui

# Chat with your codebase
uv run agent-pump ask "How does the orchestrator work?" ./my-project
```

### Development & Testing
```bash
# Run tests
uv run pytest

# Linting
uv run ruff check .

# Type checking
uv run pyright
```

## Development Conventions

### Project Structure
- `src/agent_pump/`: Main source code.
  - `orchestrator/`: Workflow engine and state machine logic.
  - `backends/`: LLM provider integrations (Gemini, Claude, etc.).
  - `models/`: Pydantic data models for configuration and state.
  - `tui/`: Textual-based terminal user interface components.
  - `api/`: FastAPI routes and server implementation.
  - `services/`: Business logic for various subsystems (cost tracking, templates, etc.).
- `tests/`: Comprehensive test suite including unit, integration, and TUI tests.

### Engineering Standards
- **Conventional Commits**: The agent automatically generates and expects conventional commit messages.
- **Automated Verification**: Every change must pass the configured `test_command`, `lint_command`, and `build_command`.
- **Living Roadmap**: Development is driven by `ROADMAP.md`. The agent reads "Current Sprint" to identify tasks.
- **State Management**: Project state is persisted in `.agent-pump/states/` and configuration in `.agent-pump/config.yml`.
- **Workspaces**: Supports multiple workspaces to isolate project sets, cost tracking, and idea queues.

### Backend Configuration
Backends are configured via `.agent-pump/config.yml` or globally. Supported providers include Gemini, Claude, and OpenCode. API keys must be provided as environment variables (e.g., `GOOGLE_API_KEY`).
