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
| **Focus vs Selection** | Use CSS classes (`.selected`) for app state, not `:focus` pseudo-classes. |
| **Testing Apps** | Inline `async with App().run_test() as pilot:` per test case; don't share app fixtures. |

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

---

## Pydantic & Config Patterns

- Use `BackendInstance(name="gemini", args=["--model", "gemini-2.5-flash"])` to separate config from runtime
- Add optional fields with defaults for backward compatibility: `planning_base: str = ""`
- Use prefix/suffix pattern for prompt customization: `prefix + base_prompt + suffix`
- Access nested config safely: guard with `if project_config and project_config.phase_backends...`
- Lambda closure bug: capture loop variables explicitly: `lambda msg, p=path: self._log(msg, p)`

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

## Verification Checklist

Before committing:
- [ ] All tests pass: `uv run pytest`
- [ ] No lint errors: `uv run ruff check .`
- [ ] Types check: `uv run pyright`
- [ ] Tested on Windows (primary dev platform)
- [ ] Updated ROADMAP.md if feature complete
- [ ] Updated this document with any lessons learned
