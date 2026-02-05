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
- **Semantic Colors**: Always use semantic variables (`$success`, `$error`, `$primary`, `$text`) instead of hardcoded colors.
- **Buttons**: Use standard variants that map to semantic colors (`variant="success"`, `variant="error"`).
- **Text Styles**: Use utility classes like `.dim` or `.error` instead of inline styles or markup.
- Ensure contrast ratios are readable

### Layout
- Use relative sizing (fr units) over absolute
- Test at different terminal sizes
- Support minimum 80x24 terminal

### Textual-Specific

| Topic | Guidance |
|-------|----------|
| **CSS Variables** | Only use standard Textual variables (`$primary`, `$surface`, `$text`, `$background`) and defined semantic variables. Forbidden: hardcoded hex/names in Python. |
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

### Preview & Dry Run Patterns
- **User Trust**: For complex or destructive operations (like Bootstrapping or applying Templates), always offer a "Preview" or "Dry Run" mode.
- **Visual Confirmation**: Display a summary of changes (e.g., "3 files will be created") before execution.
- **UI State Feedback**: Use visual cues like the `shake` animation for invalid inputs to provide immediate, non-blocking feedback.

### Form Validation
- **Input Models**: Use Pydantic models for verifying form input correctness (e.g., path existence, string length) to separate validation logic from UI code.
- **Visual Feedback**: Provide immediate feedback using classes (e.g., `.error`), animations (shake), and context-sensitive labels below fields.
- **Clear on Change**: Always clear error states immediately when the user modifies the input to signal "editing in progress". Do not re-validate on every keystroke if validation is expensive or noisy; wait for submit or debounce.

### Accessibility
- **Accessible Names**: All custom widgets must define an `accessible_name` attribute that describes their purpose and current state for screen readers.
- **Tooltips**: Use tooltips on icon-only buttons to provide both a description and keyboard shortcut hint (e.g., "Add Project (a)").
- **Contrast**: Ensure all text colors meet WCAG 4.5:1 contrast ratio against their background. Test with `$text-muted` on dark backgrounds.

### Focus Management
- **Visual Indicators**: Always define explicit `:focus` styles for interactive elements (buttons, inputs, cards). Use distinct border colors (e.g., `$accent`, `$text-inverse`) or background shifts to make the focused element unmistakable.
- **Tab Order**: Ensure logical tab order (top-left to bottom-right) in modals and forms. Verify that no "focus traps" exist where keyboard users cannot exit a widget.

### Rich Renderables
- **Use Rich Objects**: Prefer Rich `Table`, `Panel`, and `Syntax` objects over raw text or markdown for structured data and logs.
- **RichLog vs TextArea**: Use `RichLog` for append-only logs that require rich formatting (colors, tables). Use `TextArea` only for editable content or when selection/copying is the primary interaction (though RichLog supports selection too).
- **Filtering**: When using `RichLog`, you cannot "hide" lines. You must maintain a source list of renderables and clear/rewrite the log to implement filtering.

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

### Worker Thread Safety
- **Async over Threads**: Prefer `async def` methods with `run_worker()` over threaded workers (`@work(thread=True)`) whenever possible. Async workers run on the main thread and can safely modify the UI.
- **Event-Based Updates**: If a worker must run in a separate thread (e.g. blocking I/O), strictly avoid modifying UI widgets directly. Instead, publish events to an `EventBus` or use `self.post_message()` to send data back to the main thread.
- **Message Passing**: Ensure all worker-to-UI communication uses typed `Message` or `Event` classes to maintain type safety and avoid race conditions.

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

### Git Strategy & Maintenance
- **Logical Commits**: When committing large batches of changes, group them into logical commits based on feature boundaries (e.g., "Validation & Animations", "Accessibility", "Log Service") rather than one giant commit. This makes the project history easier to follow and revert if needed.
- **Context Preservation**: Keep separate "engineering plans" and "task names" for the current session, but remove or archive them once the task is fully committed to keep the root directory clean.

### Micro-interactions & Animations
- **Visual Feedback**: Small animations like shaking an input field on error or pulsing an active node significantly improve the user experience.
- **Implementation**: Simple timer-based animations (`set_timer` with incremental offsets or `set_interval` for pulsing) are often more than enough for TUI polish without needing heavy animation engines.

### UI Snapshot Pattern
- **Decoupling**: Using a dedicated `Snapshot` model (e.g., `WorkflowSnapshot`) for UI visualization decouples the UI widgets from the complex internal state machines.
- **Consistency**: A snapshot ensures that different UI implementations (TUI, Web, Mobile) all render the same state consistently using the same data contract.
- **Testability**: Snapshots are easy to unit test and mock, allowing for testing UI rendering without running the full background logic.

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

### TUI Interactivity & Events
- **Decoupled Business Logic**: When adding interactivity to complex visualizations (like workflow diagrams), use custom `Message` classes and the `@on` decorator in the parent `App` or `Screen` to handle events. This decouples the visual widget from the underlying business logic.
- **Deep Linking**: Support passing initial state (like `initial_phase`) to modals to allow "deep linking" from other parts of the UI, improving user workflow efficiency.

### Textual Widget Testing
- **Label Content**: Textual's `Label` widget does not strictly expose a public `renderable` or `text` attribute in all versions. For testing, checking for side effects (like visibility classes) or using specific query selectors is often more robust than inspecting internal renderables.
- **Mocking App Context**: When unit testing widgets that rely on an active `App` context (e.g., scrolling methods like `scroll_home()`), mock these methods (`widget.scroll_home = MagicMock()`) to test logic in isolation without spinning up a full `App` instance.

### RichLog Migration
- **API Differences**: Moving from `TextArea` to `RichLog` requires API updates. `TextArea` uses `text` property and `insert()`, while `RichLog` uses `write()`.
- **Scrolling**: Both widgets use `scroll_home()` / `scroll_end()`, but these methods require an active `App` context (animator), which can break unit tests if not mocked.
- **Renderables**: `RichLog` can accept any Rich renderable (Panel, Table) directly, whereas `TextArea` only accepts strings. This makes `RichLog` superior for logs but harder to filter (requires rebuild) compared to just hiding lines (if that were supported).

### FastAPI Server Patterns
- **Lifespan Management**: Use `@asynccontextmanager` for proper startup/shutdown handling. This ensures services are initialized before accepting requests and cleaned up gracefully on shutdown.
- **Middleware Ordering**: Add CORS before Auth middleware to ensure preflight requests are handled before authentication checks.
- **Debug Mode Toggle**: Use a `debug` parameter in `create_server()` to conditionally enable docs and detailed error responses. Never expose detailed errors in production.
- **Factory Pattern**: Create a `create_server()` factory function rather than a global app instance. This allows testing with different configurations and avoids global state issues.
- **DTOs for API Responses**: Always use Pydantic DTOs for API responses to ensure consistent serialization and validation. Never return internal domain models directly.
- **WebSocket Connection Manager**: Implement a global connection manager class to track active WebSocket connections. This enables future broadcasting capabilities and proper cleanup on disconnect.
- **TestClient for Testing**: Use FastAPI's `TestClient` for unit/integration tests. It handles the lifespan context manager automatically, making tests simpler and more reliable.
- **CLI Integration**: When adding server commands to CLI, use `asyncio.run()` to bridge sync CLI entry points with async server code. Handle signals gracefully for clean shutdown.

### Circular Import Prevention
- **Package Initialization Order**: Always define module-level constants (like `__version__`) BEFORE importing submodules in `__init__.py`.
- **Import Chain Awareness**: Be careful with import chains. A common pattern that causes circular imports: `__init__.py` imports `cli` → `cli` imports `app` → `app` imports `services` → `services` imports `api` → `api` imports `__version__` from the package root.
- **Solution**: Define `__version__` at the top of `__init__.py` before any imports, or use lazy imports (import inside functions) for breaking circular dependencies.

### API DTO Conventions
- **CamelCase for JSON**: All API DTOs must use camelCase for JSON serialization to align with JavaScript/Web standards.
- **Implementation**: Use `pydantic.alias_generators.to_camel` with `ConfigDict(alias_generator=to_camel, populate_by_name=True)`.
- **Benefits**: This allows Python code to use snake_case while the API returns camelCase for frontend compatibility.

### CORS Testing
- **Origin Header Required**: When testing CORS with TestClient, always include an `Origin` header in requests to trigger CORS middleware response headers.
- **Example**: `client.get("/health", headers={"Origin": "http://localhost:3000"})`

### Verification & Code Quality Maintenance
- **Run verification commands regularly**: `ruff check src/agent_pump` and `pyright src/agent_pump` should pass before commits.
- **Fix linting errors promptly**: Address line length (E501), whitespace (W293), unused imports (F401), and dead code (F841) as they appear.
- **Handle type checker edge cases**: Pyright is strict about:
  - Return type mismatches (e.g., `dict[str, str]` vs `dict[str, Any]`)
  - Union types that include `None` (use proper null checks)
  - Widget event handlers (check for `None` before accessing attributes)
- **Fix long lines early**: Break long strings and function calls across multiple lines before they accumulate.
- **Use explicit re-exports**: For package `__init__.py` files that re-export classes, use `from .module import Class as Class` pattern to satisfy type checkers.

### TUI Testing
- **Mocking Helpers**: When testing TUI screens that use helper functions (like `shake`), mock the imported function directly (`patch("agent_pump.tui.screens.screen.shake")`) rather than patching it as a method on the screen instance.
- **Widget Selection**: When `query_one()` is called multiple times in the code under test, use `side_effect` with a callable or list to return distinct mock widgets for each selector. This ensures assertions target the correct widget.
- **Path Resolution**: On Windows, `pathlib.Path` comparisons can be tricky due to drive letters. Always use `.resolve()` in tests when comparing paths that have been processed by application logic, or relax assertions to check normalized path components.

### Service State Management
- **Persistence of Transients**: Services that manage transient requests (like approvals) should consider how clients will query the status *after* resolution.
- **Resolution Cache**: Implementing a short-lived cache (e.g., `_resolved_approvals`) allows clients to safely query the final state of an operation even after it has been removed from the active pending list.
- **Wait Operations**: Async `wait` operations should check both pending and resolved states to avoid race conditions where an operation completes before the waiter wakes up.

### Select Widget Type Handling
- **NoSelection handling**: When using `Select` widgets, the `.value` property can return a `NoSelection` type when nothing is selected.
- **Type-safe extraction**: Always check `isinstance(value, str)` before using Select values to satisfy type checkers.
- **Example**:
  ```python
  priority = self.query_one("#item-priority", Select).value
  priority_value = None
  if isinstance(priority, str):
      priority_value = priority
  self.dismiss((title, priority_value))
  ```

### Event Handler Safety
- **Null checks for event.widget**: In `on_click` and other event handlers, `event.widget` can be `None`.
- **Safe attribute access**: Always check `if event.widget and event.widget.id == "..."` before accessing widget attributes.
- **Example**:
  ```python
  def on_click(self, event: events.Click) -> None:
      if event.widget and event.widget.id == "btn-config":
          event.stop()
          self.post_message(self.BackendConfigRequested(self.project, self))
  ```

### Commit Strategy
- **Atomic Commits**: Ensure commits are atomic and represent a single logical change or feature.
- **Pre-commit Checks**: Always run `git status` and `git diff` before committing to verify exactly what is being staged.

### TUI Chat Implementation
- **RichLog Output**: `RichLog` adds new entries for each `write()` call. For streaming content that should appear on a single line or block, accumulate the content and write it once, or use a custom widget strategy if character-by-character streaming is required.
- **Async Interactions**: Testing async UI interactions (like `Input.Submitted`) requires ensuring the widget is focused and the event loop has time to process (`pilot.pause()`).
- **File Writing**: When writing Python code that generates files with literal newlines (e.g., inside f-strings), ensure newlines are properly escaped (`\\n`) in the source string to avoid syntax errors in the generated file.

### TUI Development
- **Keyboard Navigation**: Ensure keyboard navigation is consistent across screens (e.g., `j`/`k` for lists, `Escape` to close modals).
- **Focus States**: Always provide visual feedback for focus states to guide the user.

### Git Commit Hygiene
- **Diff Verification**: Carefully review the total diff before committing to ensure no accidental deletions or sensitive information leaks.
- **Atomic Commits**: Group related changes into atomic commits that represent a single logical change or feature. This makes the history easier to follow and simplifies potential reverts or cherry-picks.
- **Staging by Feature**: When working on multiple features simultaneously (common in agentic workflows), use `git add <file>` or `git add -p` to stage changes selectively rather than `git add .`, ensuring each commit remains focused.

### Python Syntax in Tests
- **Multi-line Context Managers**: Use parentheses for multi-line `with` statements (Python 3.10+) instead of backslashes. It is cleaner and less prone to syntax errors during refactoring or tooling updates.
  ```python
  # Good
  with (
      patch("module.Thing1") as mock1,
      patch("module.Thing2") as mock2
  ):
      ...
  ```
- **Pydantic Validation in Tests**: When instantiating Pydantic models in tests, ensure all required fields (like `path` in `ProjectConfig`) are provided, even if they seem irrelevant to the specific test case. `ValidationError` will block test collection/execution.

### Verification Command Best Practices
- **Optional Imports**: Use `try/except ImportError` blocks for optional dependencies (like `psutil`) rather than `importlib.util.find_spec`, especially when compatibility with mocked `sys.modules` in tests is required.
- **Mock Naming**: When capturing mocks in `with` statements, use snake_case names (e.g., `mock_service_cls`) instead of PascalCase (e.g., `MockService`) to comply with `N806` naming conventions.
- **Breaking Long Lines**: When fixing `E501` (line too long), ensure that split lines remain syntactically valid. For `patch.object` calls, use parentheses to wrap arguments across multiple lines.