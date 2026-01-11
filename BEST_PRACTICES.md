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
- Use structured logging with `extra` dict
- Include correlation IDs for tracing
- Log at appropriate levels:
  - `DEBUG`: Detailed internal state
  - `INFO`: Important state changes
  - `WARNING`: Recoverable issues
  - `ERROR`: Failures requiring attention

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

---

## Verification Checklist

Before committing:
- [ ] All tests pass: `uv run pytest`
- [ ] No lint errors: `uv run ruff check .`
- [ ] Types check: `uv run pyright`
- [ ] Tested on Windows (primary dev platform)
- [ ] Updated ROADMAP.md if feature complete
- [ ] Updated this document with any lessons learned
