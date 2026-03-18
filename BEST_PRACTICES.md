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

### Type Hints & Python 3.12+ Control Flow
- **Always** use type hints for function signatures.
- Use `|` union syntax (Python 3.10+), not `Union`.
- Prefer `list[str]` over `List[str]`.
- Use `Path` from pathlib, not string paths.
- Use `match/case` statements for complex branching logic, especially state machines and message handling, instead of long `if/elif/else` chains.

### Async Patterns
- Use `async`/`await` for I/O operations.
- Use `asyncio.create_task()` for concurrent operations.
- **TimeoutError in Loops**: Catch `TimeoutError` **inside** the loop with `continue`, not outside.
- Handle cancellation gracefully with flags, not exceptions.

### Error Handling & Logging
- Use custom exception types for domain errors.
- Never swallow exceptions silently.
- **Log Levels**: 
  - `DEBUG`: Internal state, variable values, loop iterations.
  - `INFO`: State transitions, operation start/complete.
  - `WARNING`: Recoverable issues, fallback behavior triggered.
  - `ERROR`: Operation failures, exceptions caught.
- **Backend/Subprocess Logging Pattern**: Log the command being executed (sanitize secrets), process ID after spawn, periodic status while waiting, and final result with metrics (line count, elapsed time, exit code).

### Type Checking Nuances (Pyright)
- **Protocols and Async Generators**: Define Protocol methods returning async generators as `def run(...) -> AsyncIterator[T]`, NOT `async def`.
- **Lambdas**: Strictly check lambda signatures when passed as callbacks. Ensure lambda arguments match exactly.
- **String Joining**: Ensure arguments to `str.join` are iterables of strings.
- **Return Type Mismatches**: Be careful with return type hints in `textual` widgets. Handle edge cases like union types that include `None`.

### Multi-File Edits and Bulk Replacements
- When making bulk replacements across many lines, prefer targeted single-line edits over large multi-chunk replacements.
- Always re-read the file after failed or partial replacements to understand the current state before attempting fixes. Be extremely careful with indentation when using replace on multi-line blocks.

---

## Testing Standards

### Running & Writing Tests
- **ALWAYS** use `uv run pytest` to execute tests. Do NOT rely on global python or manually activated venvs.
- Test one thing per test with descriptive names (e.g., `test_parse_roadmap_with_empty_file_returns_empty_list`).
- Mock external dependencies (gemini-cli, git, filesystem).
- Use fixtures for test projects and clean up after integration tests (mark with `@pytest.mark.integration`).

### Async & TUI Test Best Practices
- Mark async tests with `@pytest.mark.asyncio`.
- Inline app setup in each test (`async with App().run_test() as pilot:`); don't share `App()` instances across fixtures.
- Use `side_effect` to throw `CancelledError` or break loops after N iterations.
- **Mocking Helpers**: When testing TUI screens, mock the imported function directly (e.g., `patch("agent_pump.tui.screens.screen.shake")`).
- **Widget Selection**: Use `side_effect` with a callable or list for multiple `query_one()` calls to return distinct mock widgets.
- **Mocking Async Iterators**: Correctly mock `async for` loops by using a local async generator function as the return value of `__aenter__`.

### Python Syntax in Tests
- **Multi-line Context Managers**: Use parentheses for multi-line `with` statements (Python 3.10+) instead of backslashes.
- **Mock Naming**: Use snake_case names (e.g., `mock_service_cls`) instead of PascalCase for captured mocks.
- **Pydantic Validation in Tests**: Ensure all required fields are provided when instantiating models to avoid `ValidationError`.

---

## TUI & Textual Guidelines

### Architecture & Composition
- **Decoupled Business Logic**: Use custom `Message` classes and the `@on` decorator to decouple visual widgets from underlying business logic.
- **UI Snapshot Pattern**: Use a dedicated `Snapshot` model (e.g., `WorkflowSnapshot`) to decouple UI visualization from internal state machines, ensuring consistency across different UI implementations.
- **Avoid MountError**: Instantiate containers with children (e.g., `Horizontal(child1, child2)`) rather than mounting children imperatively.
- **Dynamic Rebuilds**: Collect all new children into a list and pass them to the container constructor to avoid mounting errors during complex updates.
- **Event Handler Safety**: Check `if event.widget:` before accessing widget attributes in `on_click` and other event handlers.

### Responsiveness & Layout
- Never block the main thread. Use `async def` methods with `run_worker()` over threaded workers whenever possible.
- If a worker must run in a separate thread, strictly avoid modifying UI widgets directly. Publish events to an `EventBus` or use `self.post_message()`.
- Use relative sizing (fr units) over absolute and test at different terminal sizes (support minimum 80x24).

### State & Feedback
- **Transient State**: Store transient detailed state (like "current tool call") in memory only; clear it on phase transitions or timeouts.
- **Visual Confirmation**: For complex or destructive operations, offer a "Preview" or "Dry Run" mode. Use `ConfirmModal` for irreversible actions.
- **Micro-interactions**: Use small animations like shaking an input field on error or pulsing an active node to improve UX.
- **Form Validation**: Use Pydantic models for verifying input correctness. Provide immediate visual feedback and clear error states on user modification.

### Specific Widget Nuances
- **RichLog vs TextArea**: Use `RichLog` for append-only, richly formatted logs. Use `TextArea(read_only=True)` for selectable/editable content. RichLog requires complete rebuilding to implement filtering.
- **Select Widget**: Always check `isinstance(value, str)` before using Select values, as they can return a `NoSelection` type.
- **ListView Reordering**: Requires clearing and rebuilding the list via `clear()` and `append()`.

### Accessibility & Styling
- Always use semantic variables (`$success`, `$error`, `$primary`, `$text`) instead of hardcoded colors.
- Define explicit `:focus` styles for interactive elements.
- All custom widgets must define an `accessible_name` attribute for screen readers.
- Ensure logical tab order and check that text colors meet WCAG 4.5:1 contrast ratios.

---

## Cross-Platform Considerations

### Path Handling
- Always use `pathlib.Path`, never hardcode path separators, and use `Path.home()` for user directories.
- On Windows, `pathlib.Path` comparisons can be tricky due to drive letters. Always use `.resolve()` in tests.

### Windows Subprocess & CLI Compatibility
- Always use `encoding="utf-8"` with `Path.write_text()` for Unicode content.
- **CREATE_NO_WINDOW**: Always pass `creationflags=subprocess.CREATE_NO_WINDOW` on Windows when using `asyncio.create_subprocess_exec()` to prevent terminal popups.
- **Shell=True**: When running npm/node scripts via `subprocess.run` or `subprocess.Popen` on Windows, `shell=True` is often required because they are batch files/cmd scripts.
- **Streaming Output**: For long-running CLI operations, use `subprocess.Popen` with `stdout=subprocess.PIPE` and `stderr=subprocess.STDOUT` to stream real-time progress. Use `shutil.which` to find executables.
- The absence of output on Windows doesn't necessarily indicate failure; verify functionality through direct code inspection.

---

## Git & Version Control

### Commit Strategy
- **Atomic Commits**: Group related changes into atomic commits that represent a single logical change or feature. Ensure commits are focused and logically separated.
- **Commit Messages**: Use conventional commits format. Keep the subject under 72 characters. Provide clear descriptions of *why* the change was made.
- **Squashing Checkpoints**: Squash intermediate auto-checkpoints into a single, well-descriptive feature commit before finalization.

### Hygiene & Maintenance
- **Pre-commit Checks**: Always run `git status` and `git diff` before committing to verify exactly what is being staged and prevent sensitive information leaks.
- **Staging by Feature**: Use `git add <file>` or `git add -p` to selectively stage changes when working on multiple features simultaneously.
- **Workspace Hygiene**: Keep separate "engineering plans" and "task names" for the current session, but remove or archive them once the task is fully committed to keep the root directory clean. Never commit `.gemini/`, virtual environments, or IDE settings.

---

## Pydantic V2 & Data Modeling

### Configuration & Validation
- **ALWAYS** use `model_config = ConfigDict(...)` instead of the nested `class Config:` pattern.
- Enable `strict=True` for internal domain models and `frozen=True` for immutable models (state).
- Use `@field_validator` and `@model_validator(mode='after')` decorators. Do NOT use V1 `@validator`.
- Use `model_dump()` and `model_dump_json()`. Avoid `.dict()` and `.json()`.

### API Architecture & DTOs
- **Strict Boundary**: The API layer must be the **only** contract between the server core and clients. Never return internal domain models directly to clients.
- **Factory Pattern**: Use `from_internal(cls, model)` class methods on DTOs for conversion logic.
- **CamelCase**: All API DTOs must use `camelCase` for JSON serialization using `pydantic.alias_generators.to_camel` for frontend compatibility.

---

## Verification & Code Quality

### Verification Commands
- Run verification commands in sequence: build → lint → test.
- Include security validation to prevent command injection (e.g., validate user-provided commands against `||`, `&&`, `$()`).
- Implement auto-detection logic for common project types (npm, cargo, go, uv, etc.) using Pydantic models for configuration.

### Code Quality Maintenance
- **Checklist before committing**:
  - All tests pass: `uv run pytest`
  - No lint errors: `uv run ruff check .`
  - Types check: `uv run pyright`
- Address linting errors promptly, including line length (E501), whitespace (W293), and unused imports (F401). Break long lines across multiple lines syntactically.
- Always check existing implementation before assuming a feature is incomplete.

---

## Backend Integration & External APIs
- **CLI Invocation**: Use headless/auto-approve flags (e.g., `gemini --yolo` with prompt via **stdin**) to prevent hangs. Log the full command line.
- **Fallback & Quota**: Use Python's `Protocol` for duck-typed interfaces. Parse backend output for `[ERROR]` markers or quota indicators (`"429"`, `"rate limit"`).
- **SDK Inspection**: Write small scripts to inspect `dir(obj)` and `inspect.signature(obj)` to understand API surface areas when documentation is scarce.

### FastAPI Server Patterns
- Use `@asynccontextmanager` for lifespan management to ensure proper initialization and cleanup.
- Create a `create_server()` factory function rather than a global app instance to allow testing with different configurations.
- Ensure CORS middleware is added before Auth middleware. Include an `Origin` header when testing CORS with TestClient.

---

## State & Content Management

### Persistence & Resets
- Ensure atomic updates of both the in-memory object and the persisted state file.
- Design state loading to be robust against partial writes or missing files. Fallback to safe defaults if data is corrupt.
- Use explicit reset mechanisms (e.g., `reset_workflow()`) rather than manual file deletion.
- Prefer loading projects from `Workspace` rather than global `AppState` for contextual isolation.

### Documentation & Roadmap Maintenance
- **Partial Updates**: When updating markdown files (like `ROADMAP.md`), parse the entire file into sections and reconstruct it to avoid data loss.
- **Regex Robustness**: Use non-greedy matchers `.*?` combined with clear delimiters to robustly isolate sections.
- **Synchronization**: Always ensure `ROADMAP.md` and `docs/features.md` are updated immediately after feature implementation.
- Move completed features to the completed section to maintain clarity and drive future development priorities.

---

## Lessons Learned

* **State Persistence in Transients**: Services managing transient requests (like approvals) should use a short-lived cache so clients can safely query final status after resolution.
* **Pytransitions State Machines**: Declare `state: str` as a class attribute for type checker compatibility. Avoid string-replace hacks for trigger naming; use the full phase name explicitly.
* **Circular Import Prevention**: Define module-level constants (like `__version__`) BEFORE importing submodules in `__init__.py`. Use explicit re-exports (`from .module import Class as Class`) to satisfy type checkers.
* **F-Strings and Newlines**: Do not put literal newlines inside f-strings within Python code generated by tools. Use `\n` or triple-quoted strings to avoid `SyntaxError`.