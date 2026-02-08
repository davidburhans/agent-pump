
## 🎣 Webhook Triggers

Start workflows from external events like GitHub push or Slack commands.

### Features
- **GitHub Integration**: Automatically trigger workflows on push events to specific branches.
- **Slack Integration**: Trigger workflows via slash commands (`/agent-pump start <project>`).
- **Signature Validation**: Secure HMAC validation for all webhooks.
- **Background Processing**: Webhooks start workflows asynchronously without blocking response.

### Configuration
Configure webhooks in your workspace settings:

```yaml
webhook_config:
  enabled: true
  secret_key: "your-secret-key"
  allowed_sources: ["github", "slack"]
  auto_trigger_branches: ["main", "master"]
```

### Usage
- **GitHub**: Configure a webhook pointing to `/api/trigger/github`.
- **Slack**: Configure a slash command pointing to `/api/trigger/slack`.

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/api/routes/webhooks.py`, `src/agent_pump/models/webhook_config.py`
- **Tests**: `tests/unit/api/test_webhooks.py`, `tests/unit/models/test_webhook_config.py`
- **Documentation**: Complete

## 🔧 Auto-Fix CI Failures

Automatically detect and attempt to fix CI failures.

### Features
- **CI Watcher**: Monitors GitHub Actions for build failures.
- **Log Parsing**: Parses build logs to identify common errors (Python, TypeScript, Rust, etc.).
- **Auto-Fix Tasks**: Creates high-priority roadmap tasks with suggested fixes and error details.
- **Workflow Trigger**: Automatically starts the agent workflow to implement the fix.
- **Smart Retries**: Prevents infinite loops by tracking consecutive failures on the same branch.

### Configuration
Enabled automatically when GitHub Webhooks are configured with `check_run` events.

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/integrations/ci_watcher.py`, `src/agent_pump/integrations/failure_parser.py`, `src/agent_pump/integrations/auto_fix.py`
- **Tests**: `tests/integrations/test_ci_watcher.py`, `tests/integrations/test_failure_parser.py`, `tests/integrations/test_auto_fix.py`

## 👀 File Watcher Trigger

Trigger workflows automatically when files change.

### Features
- **Real-time Monitoring**: Uses `watchfiles` to efficiently monitor project directories.
- **Debouncing**: Waits for changes to settle before triggering (configurable).
- **Pattern Filtering**: Supports glob patterns for inclusion and exclusion.
- **Flexible Actions**: Can trigger verification (tests) or full agent workflow.

### Configuration
Configure in workspace settings or via API:

```json
"file_watcher": {
  "enabled": true,
  "patterns": ["*.py", "*.js"],
  "ignore_patterns": [".git", "__pycache__", "node_modules"],
  "debounce_seconds": 2.0,
  "action": "verification"
}
```

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/services/file_watcher_service.py`
- **Tests**: `tests/unit/test_file_watcher_service.py`

## 📊 Code Coverage Integration

Visualize code coverage directly in the TUI and use it as a verification gate.

### Features
- **Auto-Detection**: Automatically detects coverage command for uv, Python, Cargo, Go, Maven, Gradle.
- **TUI Visualization**: Displays coverage percentage in the project card.
- **Verification Gate**: Fails the verification phase if coverage drops below a configured threshold.
- **Generic Parsing**: Supports standard output formats from pytest-cov, cargo-tarpaulin, go test, and Jest.

### Configuration
Configure in Project Settings > Verification:

- **Coverage Command**: e.g., `uv run pytest --cov`, `cargo tarpaulin`
- **Threshold**: Minimum percentage required (e.g., 80.0). Set to 0 to disable gating.

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/models/verification_config.py`, `src/agent_pump/utils/coverage_parser.py`, `src/agent_pump/orchestrator/verification_executor.py`
- **Tests**: `tests/unit/utils/test_coverage_parser.py`, `tests/unit/test_verification_config.py`, `tests/unit/test_verification_executor.py`
