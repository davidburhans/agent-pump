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
| Language | Python 3.12+ | Modern async, type hints, broad ecosystem |
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
- **TimeoutError in Loops**: Catch `TimeoutError` **inside** the loop with `continue`, not outside
- Handle cancellation gracefully with flags, not exceptions

```python
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
class WorkflowError(Exception):
    """Base exception for workflow errors."""
    pass

class PlanningFailed(WorkflowError):
    """Raised when planning phase fails."""
    pass
```

### Logging
- `DEBUG`: Internal state, variable values, loop iterations
- `INFO`: State transitions, operation start/complete
- `WARNING`: Recoverable issues, fallback behavior triggered
- `ERROR`: Operation failures, exceptions caught

**Backend/Subprocess Logging Pattern:**
1. Command being executed (sanitize secrets)
2. Process ID after spawn
3. Periodic status while waiting (every 1-5s)
4. Final result with metrics (line count, elapsed time, exit code)

```python
logger.info(f"Starting Gemini CLI in {project_path}")
logger.debug(f"Command: gemini --yolo --prompt <{len(prompt)} chars>")
# ... run process ...
logger.info(f"Gemini CLI completed: {line_count} lines in {elapsed:.1f}s, exit code: {return_code}")
```

### Type Checking Nuances (Pyright)
- **Protocols and Async Generators**: `pyright` can be strict about `Protocol` definitions matching implementation.
  - If implementation is an async generator (`async def` with `yield`), define Protocol method as `def run(...) -> AsyncIterator[T]`, NOT `async def`.
  - `async def` in Protocol implies a Coroutine return type, which mismatches async generator return type (`AsyncIterator`).
- **Lambdas**: `pyright` strictly checks lambda signatures when passed as callbacks. Ensure lambda arguments match the expected callback signature exactly.
- **String Joining**: Ensure arguments to `str.join` are iterables of strings. Pydantic models or other objects must be converted to strings (e.g., `[b.name for b in backends]`) before joining.
- **Return Type Mismatches**: Be careful with return type hints in `textual` widgets. If returning a specific widget subclass (e.g., `Horizontal`), hint it as such, or ensure it is correctly imported/available.

---

## Testing Standards

### Running Tests
**ALWAYS** use `uv run pytest` to execute tests. Do NOT rely on global python or manually activated venvs.

### Unit Tests
- Test one thing per test
- Use descriptive names: `test_parse_roadmap_with_empty_file_returns_empty_list`
- Mock external dependencies (gemini-cli, git, filesystem)

### Integration Tests  
- Use fixtures for test projects
- Clean up after tests
- Mark with `@pytest.mark.integration`

### Async Test Best Practices
- Always mark with `@pytest.mark.asyncio`
- Inline app setup in each test (don't share `App()` instances across fixtures)
- Use `side_effect` to throw `CancelledError` or break loops after N iterations

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

### Textual-Specific

| Topic | Guidance |
|-------|----------|
| **CSS Variables** | Only use standard Textual variables (`$primary`, `$surface`, `$text`, `$background`). `$on-primary` does NOT exist. |
| **Widget IDs** | Use kebab-case (e.g., `workflow-panel`). Ensure `compose()` IDs match `query_one()` selectors. |
| **TextArea vs RichLog** | Use `TextArea(read_only=True)` for selectable logs. Use `RichLog` when styling > selection. |
| **@work Decorator** | Methods return `Worker` immediately. Mock with `MagicMock`, not `AsyncMock`. |
| **ModalScreen** | Use `ModalScreen[ReturnType]` with `self.dismiss(result)`. Add `priority=True` to bindings conflicting with TextArea. |
| **TabbedContent** | Query widgets by unique IDs like `{phase}-backend`, not tab structure. |
| **ListView Reordering** | Reordering items in `ListView` requires clearing and rebuilding the list via `clear()` and `append()`, as there is no direct "move" API for child widgets. |
| **Focus vs Selection** | Use CSS classes (`.selected`) for app state, not `:focus` pseudo-classes. |
| **Destructive Actions** | Always use `ConfirmModal` for irreversible actions (e.g., delete project, overwrite all configs). |
| **Testing Apps** | Inline `async with App().run_test() as pilot:` per test case; don't share app fixtures. |

### TUI Granular Feedback
- **Parsing Streams**: When dealing with long-running CLI agents, parse their output stream for granular activity indicators (e.g. "Running tool: read_file").
- **Transient State**: Store transient detailed state (like "current tool call") in memory only; clear it on phase transitions or timeouts.
- **Refresh Strategy**: Update the TUI immediately on activity changes, but also leverage periodic timers (like elapsed time) to pick up changes if the event stream is busy.

### TUI Widget Composition
- **Avoid MountError**: Do not call `.mount()` on a widget that hasn't been mounted itself. Instantiating a container with children (e.g., `Horizontal(child1, child2)`) is safer and cleaner than mounting children imperatively after creation.
- **Dynamic Rebuilds**: When rebuilding dynamic UIs, collect all new children into a list and pass them to the container constructor: `container = Horizontal(*new_children)`. This avoids mounting errors during complex updates.

---

## Cross-Platform Considerations

### Path Handling
- Always use `pathlib.Path`
- Never hardcode path separators
- Use `Path.home()` for user directories
- `Path(".").name` returns `""`—use `Path(".").resolve().name`

```python
# Good
config_path = Path.home() / ".config" / "agent-pump" / "config.yml"

# Bad
config_path = "~/.config/agent-pump/config.yml"
```

### Windows-Specific
- **File Encoding**: Always use `encoding="utf-8"` with `Path.write_text()` for Unicode content
- **Shell Limits**: Prefer stdin over command-line args for long content

### Process Execution
- Use `asyncio.create_subprocess_exec()` for subprocesses
- Handle different shell behaviors
- Test commands on all platforms
- **Windows `CREATE_NO_WINDOW`**: Always pass `creationflags=subprocess.CREATE_NO_WINDOW` on Windows. Without this flag, subprocesses may allocate their own console windows and write output directly to them (via `WriteConsole`) instead of through pipes, causing both terminal popups and broken output capture.

---

## Backend Integration

### CLI Invocation
- **Gemini CLI**: Use `gemini --yolo` with prompt via **stdin**
- **Qwen CLI**: Use `qwen --yolo` with prompt via **stdin**
- Always use headless/auto-approve flags to prevent hangs
- Log the full command line for debugging

### Fallback & Quota
- Use Python's `Protocol` for duck-typed interfaces
- Check output for quota indicators: `"quota exceeded"`, `"429"`, `"rate limit"`
- Parse backend output for `[ERROR]` markers; treat empty output as failure

### Command Validation
Validate user-provided commands against dangerous patterns:
- Command chaining: `||`, `&&`, `;`
- Command substitution: `$()`, backticks
- Security validation should be implemented at the model level using Pydantic validators to prevent command injection attacks

---

## Pydantic & Config Patterns

- Use `BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"])` to separate config from runtime
- Add optional fields with defaults for backward compatibility: `planning_base: str = ""`
- Use prefix/suffix pattern for prompt customization: `prefix + base_prompt + suffix`
- Access nested config safely: guard with `if project_config and project_config.phase_backends...`
- Lambda closure bug: capture loop variables explicitly: `lambda msg, p=path: self._log(msg, p)`

## Verification Command Patterns

- Use Pydantic models for verification configuration with proper validation
- Implement auto-detection logic for common project types (npm, cargo, go, uv, etc.)
- Run verification commands in sequence: build → lint → test
- Include security validation to prevent command injection
- Provide clear logging of verification results
- Allow skipping verification phases when needed
- Implement proper error handling and reporting for failed commands

---

## Pydantic V2 Standards

### Configuration
- **ALWAYS** use `model_config = ConfigDict(...)` instead of the nested `class Config:` pattern or `dict` assignment.
- Enable `strict=True` for internal domain models unless flexible parsing is explicitly required.
- Enable `frozen=True` for immutable models (preferred for state).

```python
from pydantic import BaseModel, ConfigDict, Field

class Project(BaseModel):
    model_config = ConfigDict(strict=True, frozen=False)
    
    name: str
```

### Validation
- Use `@field_validator` and `@model_validator(mode='after')` decorators.
- Do NOT use V1 `@validator`.

### Serialization
- Use `model_dump()` and `model_dump_json()`. Avoid `.dict()` and `.json()`.

---

## Textual Event Handling

### Interactive Elements
- **Do not** override `on_button_pressed` or similar generic handlers in `App`.
- **Use the `@on` decorator** for explicit event routing.

```python
from textual import on

class MyApp(App):
    @on(Button.Pressed, "#btn-start")
    def handle_start(self) -> None:
        ...
```

### Reactive State
- Use `textual.reactive.reactive` for state variables that should trigger UI repaints.
- Implement `watch_<var_name>` methods for side effects.

```python
from textual.reactive import reactive

class StatusPanel(Widget):
    status: str = reactive("idle")

    def watch_status(self, new_status: str) -> None:
        self.update(f"Status: {new_status}")
```

---

## Python 3.12+ Control Flow

### Pattern Matching
- Use `match/case` statements for complex branching logic, especially state machines and message handling.
- Avoid long `if/elif/else` chains for checking a single variable against multiple constants.

```python
# Good
match current_state:
    case "planning":
        await self.plan()
    case "implementing":
        await self.implement()
    case _:
        logger.error(f"Unknown state: {current_state}")

# Bad
if current_state == "planning":
    await self.plan()
elif current_state == "implementing":
    await self.implement()
```

---

## Git Practices

### Commit Messages
Use conventional commits format. Keep subject under 72 characters.

```
feat(workflow): add retry logic for failed gemini calls

Implements exponential backoff with jitter for transient failures.
Max retries: 3, initial delay: 1s, max delay: 30s.

Closes #42
```

### File Handling
Never commit: `.gemini/`, `__pycache__/`, `.pytest_cache/`, virtual environments, IDE settings

---

## File & Content Manipulation

### Roadmap Parsing & Updates
- **Partial Updates**: When updating a structured markdown file (like `ROADMAP.md`), parse the entire file into sections (preamble, sections by header). Reconstruct the file by combining preserved sections with updated sections to avoid data loss.
- **Regex Robustness**: Use non-greedy matchers `.*?` combined with clear delimiters (like `## Header`) to robustly isolate sections.
- **Preserve Formatting**: When re-writing files based on parsed content, strive to preserve original formatting (spacing, headers) for sections that were not modified.

---

## State Management

### Persistence & Resets
- **Atomic Updates**: When resetting state or handling transitions, ensure both the in-memory object (e.g., `ProjectWorkflow`) and the persisted state file (e.g., `state.json`) are updated to prevent desync.
- **Handling Interruptions**: Design state loading to be robust against partial writes or missing files. Use defaults and fallback to 'idle' or 'error' states if data is corrupt.
- **Explicit Resets**: Provide a clear mechanism (e.g., `reset_workflow()`) to force a clean slate, rather than relying on manual file deletion.
- **Context Isolation**: Prefer loading projects from `Workspace` rather than global `AppState` to ensure projects are scoped to their environment. `AppState.projects` can be used for global history, but the active session should rely on `Workspace.projects`.


---

## API Architecture

### Data Transfer Objects (DTOs)
- **Strict Boundary**: The API layer (`src/agent_pump/api`) must be the **only** contract between the server core and clients (TUI, Web).
- **No Internal Leaks**: Never return internal domain models (e.g., `Project`, `WorkflowState`) directly to clients. Always convert to DTOs.
- **Factory Pattern**: Use `from_internal(cls, model)` class methods on DTOs for conversion logic. This keeps the internal model clean of presentation logic.
- **CamelCase**: All API DTOs must use `camelCase` for JSON serialization to align with JavaScript/Web standards. Use `pydantic.alias_generators.to_camel`.

```python
class ProjectStatusDTO(APIBaseModel):
    name: str
    time_in_state: float = Field(alias="timeInState")

    @classmethod
    def from_internal(cls, project: Project) -> Self:
        return cls(name=project.name, ...)
```

---

## Verification Checklist

Before committing:
- [ ] All tests pass: `uv run pytest`
- [ ] No lint errors: `uv run ruff check .`
- [ ] Types check: `uv run pyright`
- [ ] Tested on Windows (primary dev platform)
- [ ] Updated ROADMAP.md if feature complete
- [ ] Updated this document with any lessons learned

## Lessons Learned

### Windows Command Line Output Issues
- On Windows systems, command output may not appear in certain shell contexts due to output buffering or redirection
- When developing on Windows, use direct Python execution or specific test runners to verify functionality
- The absence of output doesn't necessarily indicate failure; verify functionality through direct code inspection

### Feature Verification Process
- Always check existing implementation before assuming a feature is incomplete
- The ROADMAP.md status may already reflect completed work that was implemented in previous iterations
- Verify functionality exists by examining the codebase thoroughly before proceeding with implementation

### Roadmap Maintenance
- Regularly review and update the roadmap to ensure accurate status of features
- Completed features should be properly moved to the completed section to maintain clarity
- When features are completed, ensure the roadmap reflects the current state to avoid confusion
- The roadmap should be kept clean and up-to-date to guide future development priorities

### Dynamic State Machines with pytransitions
- When using `pytransitions.Machine`, the `state` attribute is dynamically added to the model. Declare `state: str` as a class attribute for type checker compatibility.
- Dynamic trigger methods (e.g., `planning_complete()`) are generated at runtime. Use `# type: ignore` comments and ensure trigger names match transition definitions exactly.
- Avoid `str.replace()` hacks for trigger naming (e.g., `"planning".replace("ing", "")` → `"plann"`). Use the full phase name directly: `f"{phase.name}_complete"`.

### Protocol Definitions for Async Generators
- When defining a `Protocol` for a class that has an async generator method, declare it as `def run(...) -> AsyncIterator[T]`, NOT `async def run(...)`.
- `async def` in a `Protocol` implies a `Coroutine` return type, which mismatches the `AsyncIterator` returned by an actual async generator.

### Multi-File Edits and Bulk Replacements
- When making bulk replacements across many lines, prefer targeted single-line edits over large multi-chunk replacements. Large replacements are prone to errors if target content doesn't match exactly.
- Always re-read the file after failed or partial replacements to understand the current state before attempting fixes.

### API & Data Contracts
- **Strict Separation of Concerns**: Maintain a hard boundary between server logic and client presentation. Using DTOs as the sole exchange format prevents internal refactors from breaking clients (TUI/Web).
- **Validation in DTOs**: Moving validation and transformation logic (like calculating `time_in_state`) into DTO factory methods simplifies the core service logic.