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

---

## Verification Checklist

Before committing:
- [ ] All tests pass: `uv run pytest`
- [ ] No lint errors: `uv run ruff check .`
- [ ] Types check: `uv run pyright`
- [ ] Tested on Windows (primary dev platform)
- [ ] Updated ROADMAP.md if feature complete
- [ ] Updated this document with any lessons learned
