# Agent Pump ⛽

Agent Pump is an advanced orchestration platform that transforms AI coding assistants into autonomous, persistent software engineering agents. It manages the entire software development lifecycle—from planning and implementation to rigorous verification, peer-review, and committing—driven by an intricate, state-driven workflow loop.

## 🚀 Project Overview & Architecture

At its core, Agent Pump acts as a continuous state machine representing an idealized software engineering workflow:

**Plan → Implement → Verify → Brainstorm/Review → Commit**

Rather than simple conversational turns, Agent Pump uses **Workspaces** to isolate state, track costs, and queue ideas. Development is fundamentally driven by a living `ROADMAP.md` document, which the agent continually references to identify and plan the next sprint's tasks.

### 🛠 Core Technologies & Stack

Agent Pump spans multiple interfaces, driven by a unified backend and multiple decoupled frontends.

#### Backend (Python 3.12+)
- **Task Orchestration**: `transitions` (state machine logic and workflow graph)
- **API & Server**: `FastAPI` + `Uvicorn` (REST API for remote integration)
- **Models & Validation**: `Pydantic` v2 (configuration, API contracts, domain models)
- **Git Integration**: `GitPython` (branching strategies, automated rebasing, checkouts)
- **Package Management & Tooling**: `uv` (dependency resolution, lockfiles, virtual environments)

#### User Interfaces
- **TUI (Terminal User Interface)**: Built with `Textual` and `Rich`, offering a full-featured visual dashboard directly in the terminal.
- **CLI (Command Line Interface)**: Powered by `Click` for headless execution, CI/CD pipelines, and fast utility commands.
- **Web UI**: A modern web dashboard located in `ui/` built with **React**, **Vite**, **Tailwind CSS**, and **TypeScript**.

---

## 🏗 Core Concepts & Subsystems

The `src/agent_pump/services/` layer handles the complex domain logic required for autonomous operations:

- **State Machine Orchestration**: Manages transitions between `Plan`, `Implement`, and `Verify`. If verification fails (e.g., tests fail), the state machine automatically loops back to `Implement` for debugging.
- **Cost Tracking & Metrics**: Tracks token usage across multiple LLM providers, providing real-time cost analysis per workspace.
- **Branch Strategy & PR Review**: Automatically creates isolated branches, evaluates code changes, and simulates automated Pull Request reviews via the `pr_review_service`.
- **Idea Queue & Collaboration**: Developers and agents can brainstorm. Ideas are queued via the `idea_service` and integrated into the overarching roadmap.
- **Checkpoints & Fallbacks**: The `checkpoint_service` takes snapshots of the workspace before major changes, allowing the agent to confidently rollback if an implementation goes astray.
- **Plugins & Templates System**: Allows dynamic extension of agent capabilities (`plugin_manager`) and standardized prompting/scaffolding (`template_service`).

---

## 💻 Building and Running

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- Node.js (v20+) & npm (for Web UI)

### Backend Setup
```bash
# Install all Python dependencies using uv
uv sync
```

### Running the Application (Backend / TUI / CLI)
```bash
# Launch the main TUI Dashboard
uv run agent-pump

# Launch the REST API server (FastAPI)
uv run agent-pump --web --web-port 8000

# Headless mode for CI/CD or background jobs
uv run agent-pump ./my-project --no-tui

# Ask a direct question about a local project
uv run agent-pump ask "How does the orchestrator work?" ./my-project
```

### Frontend Setup & Running (Web UI)
```bash
cd ui
npm install

# Start the Vite development server
npm run dev

# Build for production
npm run build
```

---

## 🧪 Testing Strategy

Agent Pump enforces rigorous verification of itself. The `tests/` directory is split strategically:

- **Unit Tests (`tests/unit/`)**: Isolated tests mocking file systems, Git, and network calls. Used extensively for verifying isolated services (`test_cost_tracking_service.py`, `test_github_service.py`).
- **Integration Tests (`tests/integration/`)**: Tests end-to-end flows, such as running the state machine through a full implementation-verification loop.
- **TUI Tests (`tests/tui/`)**: Specialized tests utilizing Textual's async pilot testing framework to programmatically interact with the terminal UI.
- **Benchmark Tests (`tests/benchmark/`)**: Evaluates performance of prompt loading and state transitions.

Run the test suite:
```bash
uv run pytest
```

---

## 📜 Development & Engineering Standards

As an AI working in this codebase, adhere strictly to the following standards:

1. **Strict Verification**: Every code modification MUST pass automated verification. The project uses `pyright` for static type checking and `ruff` for linting.
   ```bash
   uv run ruff check .
   uv run pyright
   ```
2. **Conventional Commits**: You must write conventional commit messages (e.g., `feat(orchestrator): add auto-revert transition`).
3. **Living Roadmap**: Always refer to `ROADMAP.md` before starting new architectural initiatives.
4. **State Isolation**: When introducing new logic, ensure it respects `Workspace` boundaries and persists state properly via the `models/` layer, saving to `.agent-pump/states/`.
5. **No Blind Shell Commands**: Any automated modification must be accompanied by tests that verify its success structurally and behaviorally.
6. **Backend Configuration**: Supported LLMs include Gemini, Claude, and OpenCode. Configure via `.agent-pump/config.yml` and provide keys as environment variables (e.g., `GOOGLE_API_KEY`).