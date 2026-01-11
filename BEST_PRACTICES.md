# Agent Pump - Best Practices

This document serves as the living engineering guide for developing and maintaining Agent Pump. It should be updated with lessons learned during development.

## Project Philosophy

Agent Pump automates iterative AI-assisted development. The tool must be:
- **Reliable**: Failures should be recoverable; state should persist
- **Observable**: Users must see what's happening at all times
- **Safe**: Never lose work; always use version control
- **Cross-platform**: Work identically on Windows, Linux, and macOS

---

## Tech Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | Modern async, type hints, broad ecosystem |
| Package Manager | uv | Fast, reliable, cross-platform |
| TUI Framework | Textual | Modern, async-first, CSS styling |
| Data Models | Pydantic v2 | Validation, serialization, IDE support |
| CLI Framework | Click | Declarative, composable, well-documented |
| Git Operations | GitPython | Mature, cross-platform |
| Testing | pytest + pytest-asyncio | Industry standard, async support |
| Linting | ruff | Fast, comprehensive |
| Type Checking | pyright | Strict, catches real bugs |

---

## Code Style

### Type Hints
- **Always** use type hints for function signatures
- Use `|` union syntax (Python 3.10+), not `Union`
- Prefer `list[str]` over `List[str]`
- Use `Path` from pathlib, not string paths

```python
# Good
def parse_roadmap(path: Path) -> list[Feature]:
    ...

# Bad
def parse_roadmap(path):
    ...
```

### Async Patterns
- Use `async`/`await` for I/O operations
- Use `asyncio.create_task()` for concurrent operations
- Always handle cancellation gracefully

```python
# Good
async def run_workflow(project: Project) -> None:
    try:
        await planning_phase(project)
        await implementing_phase(project)
    except asyncio.CancelledError:
        logger.info("Workflow cancelled, cleaning up...")
        raise
```

### Error Handling
- Use custom exception types for domain errors
- Log errors with context
- Never swallow exceptions silently

```python
# Good
class WorkflowError(Exception):
    """Base exception for workflow errors."""
    pass

class PlanningFailed(WorkflowError):
    """Raised when planning phase fails."""
    pass

# In code
try:
    result = await run_gemini(prompt)
except GeminiError as e:
    logger.error("Gemini failed", extra={"prompt": prompt, "error": str(e)})
    raise PlanningFailed(f"Could not create plan: {e}") from e
```

### Logging

Logging is critical for debugging issues in production. Every module should use a logger.

#### Configuration
```python
import logging
logger = logging.getLogger(__name__)
```

#### Log Levels
- `DEBUG`: Internal state, variable values, loop iterations - anything useful for tracing execution flow
- `INFO`: Important state transitions, operation start/complete, configuration loaded
- `WARNING`: Recoverable issues, fallback behavior triggered, deprecated usage
- `ERROR`: Operation failures, exceptions caught, invalid state detected

#### What to Log
- **Process lifecycle**: Start, completion, cancellation, timeout
- **External calls**: Before/after calling external tools (gemini-cli, git, etc.)
- **State transitions**: Workflow state changes, project status updates
- **Performance**: Elapsed time for long operations, line/item counts
- **Errors**: Full context including relevant variables

```python
# Good - logs process lifecycle with context
logger.info(f"Starting Gemini CLI in {project_path}")
logger.debug(f"Command: gemini --yolo --prompt <{len(prompt)} chars>")
# ... run process ...
logger.info(f"Gemini CLI completed: {line_count} lines in {elapsed:.1f}s, exit code: {return_code}")

# Good - logs waiting/retry state
logger.debug(f"Waiting for output... ({elapsed:.1f}s elapsed, {line_count} lines so far)")

# Bad - no context
logger.info("Process finished")
```

#### Backend Debugging Pattern
For subprocess execution, log:
1. Command being executed (sanitize secrets)
2. Process ID after spawn
3. Periodic status while waiting (every 1-5 seconds)
4. Final result with metrics

---


## Testing Standards

### Unit Tests
- Test one thing per test
- Use descriptive test names: `test_parse_roadmap_with_empty_file_returns_empty_list`
- Mock external dependencies (gemini-cli, git, filesystem)

### Integration Tests  
- Use fixtures for test projects
- Clean up after tests
- Can be slower; mark with `@pytest.mark.integration`

### Test Coverage
- Aim for 80%+ coverage on core logic
- Don't test trivial code (getters, simple wrappers)
- Focus on edge cases and error paths

---

## TUI Guidelines

### Responsiveness
- Never block the main thread
- Use workers for long operations
- Update UI frequently during long tasks

### Accessibility
- Support keyboard navigation for all features
- Use semantic colors (success=green, error=red)
- Ensure contrast ratios are readable

### Layout
- Use relative sizing (fr units) over absolute
- Test at different terminal sizes
- Support minimum 80x24 terminal

---

## Git Practices

### Commit Messages
- Use conventional commits format
- Keep subject line under 72 characters
- Include context in body when needed

```
feat(workflow): add retry logic for failed gemini calls

Implements exponential backoff with jitter for transient failures.
Max retries: 3, initial delay: 1s, max delay: 30s.

Closes #42
```

### File Handling
- Always use `.gitignore` patterns
- Never commit:
  - `.gemini/` artifacts
  - `__pycache__/`
  - `.pytest_cache/`
  - Virtual environments
  - IDE settings (unless shared)

---

## Cross-Platform Considerations

### Path Handling
- Always use `pathlib.Path`
- Never hardcode path separators
- Use `Path.home()` for user directories

```python
# Good
config_path = Path.home() / ".config" / "agent-pump" / "config.yml"

# Bad
config_path = "~/.config/agent-pump/config.yml"
```

### Process Execution
- Use `asyncio.create_subprocess_exec()` for subprocesses
- Handle different shell behaviors
- Test commands on all platforms

### Line Endings
- Configure git for consistent line endings
- Use `\n` in code, let git handle conversion

---

## Lessons Learned

*This section is updated as we learn from development and production usage.*

### 2026-01-10: Initial Guidelines
- Established core practices document
- Defined tech stack and rationale
- Set testing and code style standards

### 2026-01-10: TUI Debugging Session
- **Textual CSS Variables**: Only use standard Textual variables (`$primary`, `$surface`, `$text`, `$background`). Variables like `$on-primary` do NOT exist and will crash the app on stylesheet load.
- **Widget ID Consistency**: Use kebab-case for IDs (e.g., `workflow-panel`). Ensure `compose()` IDs match `query_one()` selectors exactly.
- **Backend Error Propagation**: Check output for `[ERROR]` markers and treat empty output as failure. Prevents infinite loops when backends are missing.
- **Windows File Encoding**: Always use `encoding="utf-8"` with `Path.write_text()` when writing Unicode content (emoji, special characters). Windows defaults to cp1252 which fails on non-ASCII.
- **TextArea vs RichLog**: Use `TextArea(read_only=True)` for user-selectable logs. Use `RichLog` only when rich styling is more important than selection.

### 2026-01-10: Async Reading Loop Bug
- **TimeoutError in Loops**: When using `asyncio.wait_for()` inside a `while True` loop, the `TimeoutError` exception must be caught **inside** the loop with an explicit `continue`. Catching it outside or letting it fall through exits the loop prematurely.
- **Path(".").name Returns Empty**: `Path(".").name` returns `""`, not the directory name. Use `Path(".").resolve().name` or store the resolved name during project creation.
- **Add Debug Logging Early**: Subprocess execution should log: command, PID, periodic waiting status, and final metrics. Without this, silent failures are impossible to diagnose.

### 2026-01-10: TUI ASCII Art Best Practices
- **Avoid Inline State Markers in ASCII Art**: Using f-strings to inject variable-width text (e.g., `[IDLE]` vs ` IDLE `) into ASCII diagrams breaks alignment. Instead, show the current state as a separate header line.
- **Test ASCII Art at Multiple Widths**: Box-drawing characters (║, ═, ┌, etc.) have varying widths in different terminals/fonts. Keep diagrams narrow (<50 chars) and test in the actual TUI.
- **Simple is Better**: Complex box-drawing diagrams are fragile. A clean flowchart without outer borders is more maintainable and displays consistently.
- **Textual Image Support**: Textual doesn't natively support images (on roadmap). Use `textual-image` library with Sixel/TGP protocols, but expect terminal compatibility issues. ASCII fallback is always more reliable.

### 2026-01-10: Gemini CLI Arguments
- **Check CLI Help Regularly**: Gemini CLI flags change between versions. `--prompt` is deprecated (use positional arg), `--checkpointing` doesn't exist.
- **Correct Syntax**: `gemini --yolo` - pass the prompt via **stdin** for reliable operation.
- **Stdin is Mandatory**: You **MUST** provide the input via `stdin` for `gemini-cli` to work correctly in this integration. Passing prompts as command-line arguments interacts poorly with shell quoting and length limits, especially on Windows.
- **Log Commands For Debugging**: When subprocess output is corrupted, log the full command line to a file for post-mortem debugging.

### 2026-01-10: Backend Verification
- Verified `GeminiBackend` implementation against unit tests.
- Confirmed strict adherence to async reading loop best practices (catching `TimeoutError` inside the loop).
- Confirmed prompt passing via stdin to avoid shell limitations.

### 2026-01-10: Core Infrastructure Setup
- **Pytest and Text Files**: `pytest` may attempt to collect/parse files starting with `test_` even if they have `.txt` extension if they are in the root directory. Keep the root clean or explicitly configure `testpaths`.
- **Click Command Naming**: Always explicitly set `name="app-name"` in `@click.command()` to ensure help text and `CliRunner` tests display the correct program name instead of the function name (e.g., `Usage: agent-pump` vs `Usage: main`).

### 2026-01-10: State Machine & Async Testing
- **State Logic Sync**: When using a state machine library, ensure your execution loop (e.g., `while` loop) explicitly handles every state defined in the transitions. Missing a state in the loop leads to "stuck" workflows.
- **Async Test Mocking**: Testing infinite async loops requires careful mocking. Use `side_effect` to throw `CancelledError` or break the loop after a set number of iterations to prevent test hangs.
- **State Persistence**: Pydantic models are excellent for persisting state machine context. Ensure you save state *after* every transition to recover from crashes.

### 2026-01-11: Workflow State & UI Updates
- **Reactive UI Updates**: TUI widgets (like `ProjectCard`) do not automatically update when backend state changes. You must bind state change callbacks (e.g., `on_state_change`) to explicitly refresh the UI components.
- **Workflow Resumption vs. Pause**:
  - **Quitting**: Quitting the app preserves the current phase in `state.json`. Relaunching restarts that phase from the beginning.
  - **Pausing**: "Pause" should stop the loop *without* resetting variables or transitioning state. Avoid resetting to `IDLE` or `ERROR` on pause, as this forces a restart from `PLANNING` and loses iteration progress.
- **Graceful Cancellation**: In `asyncio` loops, check for cancellation flags (e.g., `self._cancelled`) frequently. To "pause", break the loop cleanly without throwing exceptions or marking the run as a failure.

### 2026-01-11: TUI Development
- **Visual State Management**: Separating "focus" (keyboard interaction) from "selection" (active application state) is crucial in TUIs. Use dedicated CSS classes (e.g., `.selected`) for application state rather than relying on `:focus` pseudo-classes.
- **Message Passing**: When using `post_message` with custom messages, pass the widget instance (`self`) if the receiver needs to call methods on the sender.
- **Testing TUIs**: While full interaction testing requires a `Pilot`, unit testing widget logic (like formatting methods) is effective for quick validation.
- **Textual @work Decorator**: Methods decorated with `@work` become fire-and-forget. They return a `Worker` object immediately and schedule the coroutine. When mocking these methods in tests, use `MagicMock` instead of `AsyncMock` if the caller does not await them (which they shouldn't).
- **Granular Controls**: For multi-project management, provide both global (Start All) and granular (Start Selected) controls. Bindings should be intuitive (e.g., `s` for Start Selected, `Shift+S` for Start All).

### 2026-01-11: App State Persistence & Testing
- **Mocking Filesystem**: When testing code that uses `Path.mkdir` or `Path.home`, ensure your mocks (like `monkeypatch.setattr`) either create the directory structure in the tempdir or mock the paths to point to existing temp locations. Mocking `Path.home` is often cleaner than mocking specific methods like `get_state_path`.
- **Dual State Management**: When an app has both CLI and TUI components, ensure both respect the same source of truth (e.g., a persistent JSON file). Load state on startup and save on every mutation.
- **TUI State Injection**: Inject persistent state managers (like `AppState`) into the TUI application constructor rather than re-loading inside the TUI. This makes testing easier and ensures consistency if the CLI modifies state before launching the TUI.

### 2026-01-11: Fallback Backends & Workspace Configuration
- **Protocol for Duck Typing**: Use Python's `Protocol` (from `typing`) to define interfaces when multiple classes need to be used interchangeably (e.g., `AgentBackend` and `FallbackBackendRunner` both have a `run()` method).
- **Quota Detection**: When implementing fallback logic, check output for quota/rate limit indicators as strings (e.g., "quota exceeded", "429", "rate limit"). These messages vary by provider, so use multiple indicators.
- **Workspace vs AppState**: Keep `AppState` minimal (just project paths and current workspace name). Store detailed configuration in `Workspace` objects, which are saved separately per workspace.
- **Idea Queue Priority**: When implementing priority queues, sort on insertion (`add_idea`) rather than on retrieval. This keeps `peek_ideas` and `pop_ideas` simple and fast.
- **Lambda Closure Bug**: When creating callbacks in a loop, capture the loop variable explicitly: `lambda msg, p=path: self._log(msg, p)` instead of `lambda msg: self._log(msg, path)`. The latter captures the variable by reference, not value.

### 2026-01-11: Backend Args & Prompt Customization
- **Config Models vs Instances**: Use `BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"])` to keep config (name + args) separate from runtime instances. Factory functions like `from_config()` bridge the gap.
- **Prompt Composition Pattern**: Use prefix/suffix pattern for prompt customization: `prefix + base_prompt + suffix`. This is more flexible than just overrides and allows users to extend without replacing.
- **Extra Args Propagation**: When adding optional parameters like `extra_args` to method signatures, add them with `| None = None` default throughout the call chain (base class → implementation → runner → workflow).
- **Accessing Nested Config Safely**: When accessing `project_config.phase_backends.implementing.backends[0].name`, ensure all intermediate objects exist. Guard with `if project_config and project_config.phase_backends.implementing.backends:`.

### 2026-01-11: Textual Modals & TabbedContent
- **ModalScreen Pattern**: Use `ModalScreen[ReturnType]` with `self.dismiss(result)` to return values. Caller uses `push_screen(modal, callback)` to handle results.
- **Bindings in Modals**: Add `priority=True` to bindings like `Ctrl+S` that conflict with TextArea's default bindings.
- **Dynamic Widget State**: Use `on_select_changed` to enable/disable related widgets (e.g., disable fallback args when "none" selected).
- **TabbedContent IDs**: When querying widgets inside tabs, use unique IDs like `{phase}-backend` rather than relying on tab structure.

### 2026-01-11: Module Registry & Extensibility Patterns
- **Consistent Registry Naming**: When exporting a registry dict (like `BACKEND_REGISTRY`), use the same name everywhere. Renaming it (e.g., to `AVAILABLE_BACKENDS`) causes import errors and confusion.
- **Checkbox + read_only Pattern**: For "override default" UX, use a Checkbox to toggle `TextArea.read_only`. When unchecked, reset text to default and lock; when checked, unlock for editing.
- **Collapsible for Advanced Options**: Use `Collapsible(collapsed=True)` to hide advanced options (like base prompt editing) while keeping them accessible. Pair with a keyboard shortcut (e.g., `Ctrl+B`) for power users.
- **Pydantic Model Extensibility**: Add new optional fields with defaults (e.g., `planning_base: str = ""`) for backward-compatible model evolution. Empty string = "use default" is a clean pattern.


---

### 2026-01-11: TUI Global Actions & Tabs
- **Global Actions for Tabs**: When placing buttons outside of `TabbedContent` that affect the active tab (like "Add Backend"), use `query_one(TabbedContent).active` to determine the context. This avoids duplicating buttons inside every tab.
- **Tab ID Parsing**: Ensure tab IDs follow a parseable pattern (e.g., `id="tab-{phase}"`) so you can easily extract the data key (e.g., `phase`) from the active tab ID.

### 2026-01-11: Qwen CLI Integration & Tooling
- **Prefer Stdin for Piped Input**: Even if a CLI (like `qwen`) suggests using positional arguments for non-interactive mode, piping input via standard input (`stdin`) avoids OS command-line length limits and shell escaping issues. This is especially critical on Windows.
- **Headless Execution**: Always invoke agentic CLIs with their "headless" or "auto-approve" flags (e.g., `qwen --yolo`, `gemini -y`) to prevent the backend from hanging indefinitely while waiting for user confirmation.
- **Modern Python Tooling**: Use `uv` for running tests and linters (`uv run pytest`) to ensure a consistent, isolated environment without manually activating virtual environments.

### 2026-01-11: Custom Verification Commands Implementation
- **Project Model Extension**: When extending models with new functionality, ensure the model attributes match the expected access patterns. For example, when adding verification config to Project, make sure the workflow accesses it correctly (`project.config` vs `project.config.verification`).
- **Case Sensitivity in File Detection**: When detecting project types by file names, be mindful of case sensitivity differences across operating systems. Using `.lower()` on filenames helps ensure consistent detection across platforms.
- **Pydantic Model Integration**: When integrating new Pydantic models into existing systems, ensure proper imports and field definitions to maintain compatibility with existing code.
- **Command Validation**: When allowing users to specify custom commands, implement validation to prevent dangerous patterns like command chaining (`||`, `&&`), semicolons (`;`), and command substitution (`$()`, `` `cmd` ``).
- **Async Subprocess Management**: When executing subprocesses asynchronously, implement proper timeout handling and process termination to prevent hanging processes.
- **Error Reporting**: Provide clear error messages and status reports for verification command execution to help users understand what succeeded or failed.

## Verification Checklist

Before committing:
- [ ] All tests pass: `uv run pytest`
- [ ] No lint errors: `uv run ruff check .`
- [ ] Types check: `uv run pyright`
- [ ] Tested on Windows (primary dev platform)
- [ ] Updated ROADMAP.md if feature complete
- [ ] Updated this document with any lessons learned
