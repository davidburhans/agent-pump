# Custom Verification Commands

Agent-pump supports custom build, lint, and test commands that run after the AI verification phase. This allows you to ensure that your code changes meet your project's specific requirements.

## Configuration

Verification commands can be configured in two ways:

### 1. Project-Level Configuration (`.agent-pump/config.yml`)

Create a `.agent-pump/config.yml` file in your project:

```yaml
verification:
  build_cmd: "npm run build"           # Command to build your project
  lint_cmd: "npm run lint"            # Command to lint/check code style
  test_cmd: "npm test"                # Command to run tests
  skip_verification: false            # Whether to skip verification entirely
```

### 2. Through the TUI Interface

Use the verification configuration modal in the TUI to set up commands interactively.

### 3. Auto-Detection

Agent-pump can automatically detect common project types and suggest appropriate commands:

- **Rust (Cargo)**: `cargo build`, `cargo clippy`, `cargo test`
- **Node.js (npm)**: `npm run build`, `npm run lint`, `npm test`
- **Go**: `go build ./...`, `golangci-lint run`, `go test ./...`
- **Python (uv)**: `uv build`, `uv run ruff check .`, `uv run pytest`
- **Python (Poetry)**: `poetry build`, `poetry run ruff check .`, `poetry run pytest`
- **Python (Standard)**: `python -m build`, `ruff check .`, `pytest`
- **Java (Maven)**: `mvn compile`, `mvn checkstyle:check`, `mvn test`
- **Java (Gradle)**: `gradle build`, `gradle check`, `gradle test`
- **Make**: `make`, N/A, `make test`

## Security

For security reasons, the following dangerous patterns are not allowed in verification commands:

- Command chaining with `||` or `&&`
- Command separation with `;`
- Command substitution with `$()` or backticks

## Skip Verification

You can skip the verification phase entirely by setting `skip_verification: true` in your configuration. This is useful when you want to iterate quickly without running heavy build/test processes.

## Examples

### JavaScript/TypeScript Project
```yaml
verification:
  build_cmd: "npm run build"
  lint_cmd: "npm run lint"
  test_cmd: "npm run test:unit"
  skip_verification: false
```

### Rust Project
```yaml
verification:
  build_cmd: "cargo build"
  lint_cmd: "cargo clippy --all-targets --all-features"
  test_cmd: "cargo test --all-targets --all-features"
  skip_verification: false
```

### Python Project
```yaml
verification:
  build_cmd: "python -m build"
  lint_cmd: "ruff check . && mypy src/"
  test_cmd: "pytest tests/ -v"
  skip_verification: false
```

### Go Project
```yaml
verification:
  build_cmd: "go build ./..."
  lint_cmd: "golangci-lint run ./..."
  test_cmd: "go test ./... -v"
  skip_verification: false
```

## Behavior

- Verification commands run in sequence: build → lint → test
- If the build command fails, lint and test commands are skipped
- Each command has its own timeout (build/lint: 120s, test: 300s)
- Output from each command is logged to the agent output
- The workflow continues only if all verification commands pass (when not skipped)