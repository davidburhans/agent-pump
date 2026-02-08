
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

## 🛡️ Enhanced Tool Security

Secure execution environment for custom tools with fine-grained controls.

### Features
- **Interpreter Allow-list**: Restrict which interpreters (python, node, bash, etc.) can be used for custom tools.
- **Argument Validation**: Validate tool arguments using Regex patterns and enforce path restrictions.
- **Path Traversal Prevention**: Strictly prevents tools from accessing files outside the project root.
- **Sandboxing**: Optionally execute tools inside Docker containers for isolation.
- **Image Inference**: Automatically selects appropriate Docker images for Python, Node, Bash, and PowerShell tools.

### Configuration
Configure in Project Settings > Tool Security:

```json
"tool_security": {
  "enabled": true,
  "allowed_interpreters": ["python", "node", "bash"],
  "allowed_path_patterns": ["src/*", "data/*.json"],
  "allow_network_access": false
}
```

Tool Definition (in `config.yml`):
```yaml
tools:
  - name: sensitive_op
    command: python scripts/op.py
    sandbox: true
    args:
      - name: target_file
        type: path
        validation_regex: "^[a-z0-9_]+\.json$"
```

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/models/tool_security.py`, `src/agent_pump/communication/mcp_server.py`
- **Tests**: `tests/unit/test_tool_security.py`, `tests/unit/test_tool_config.py`

## 🧠 Context Awareness Improvements

Improve the context provided to agents by intelligently selecting relevant files using embeddings.

### Features
- **Semantic Search**: Uses `sentence-transformers` to generate embeddings for code chunks.
- **Incremental Indexing**: Efficiently updates the index by only re-processing changed files.
- **Prompt Injection**: Automatically injects relevant code snippets into the planning and implementing prompts.
- **Language Aware Chunking**: Uses regex-based chunking for Python and Markdown files.

### Configuration
Enabled automatically. Requires `sentence-transformers` and `scikit-learn` dependencies.
Index is stored in `.agent-pump/embeddings/`.

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/services/context_service.py`, `src/agent_pump/services/embeddings_service.py`, `src/agent_pump/services/vector_store.py`, `src/agent_pump/utils/code_chunker.py`
- **Tests**: `tests/services/test_context_service.py`, `tests/services/test_embeddings_service.py`, `tests/services/test_vector_store.py`, `tests/services/test_code_chunker.py`

## 🔗 Remote MCP Server Support

Connect to external MCP servers to extend capabilities beyond local tools.

### Features
- **Meta-Tool Architecture**: Exposes `list_remote_tools` and `run_remote_tool` to agents to discover and use remote capabilities dynamically.
- **Client Manager**: Manages persistent connections to multiple remote MCP servers.
- **Protocol Support**: Supports both `stdio` (local subprocess) and `sse` (HTTP) transport protocols.
- **Configuration**: Define remote servers in `config.yml` per project or globally.

### Configuration
Add to `config.yml`:

```yaml
mcp_servers:
  - name: "weather-server"
    type: "stdio"
    command: "uv"
    args: ["run", "mcp-weather"]
  - name: "remote-docs"
    type: "sse"
    url: "http://docs.example.com/mcp/sse"
```

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/communication/mcp_client.py`, `src/agent_pump/models/mcp_config.py`, `src/agent_pump/communication/mcp_server.py`
- **Tests**: `tests/communication/test_mcp_client.py`, `tests/models/test_mcp_config.py`

## 🦙 Ollama Backend Support

Run Agent Pump with local LLMs using Ollama.

### Features
- **Local Execution**: Use open-source models like Llama 3, Mistral, and Gemma locally.
- **Privacy First**: No data leaves your machine.
- **Streaming Support**: Real-time response streaming for interactive feedback.
- **Model Discovery**: Automatically lists available models from your Ollama instance.
- **Configuration**: Set endpoint and model via config file or environment variables.

### Configuration
Configure in `config.yml` or use environment variables:

```yaml
backend: ollama
ollama:
  endpoint: http://localhost:11434
  model: llama3
```

Or via environment:
```bash
export AGENT_PUMP_BACKEND=ollama
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=mistral
```

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/backends/ollama.py`, `src/agent_pump/models/ollama_config.py`, `src/agent_pump/config.py`
- **Tests**: `tests/backends/test_ollama.py`

## 📚 Knowledge Base Integration

Index project documentation and external resources for enhanced RAG context.

### Features
- **Documentation Indexing**: Automatically indexes markdown files in `docs/` directory.
- **External Resources**: Fetches and indexes external documentation URLs specified in config.
- **HTML Parsing**: Uses BeautifulSoup to extract clean text from external HTML pages.
- **Smart Retrieval**: Distinguishes between code, docs, and external resources in retrieved context.

### Configuration
Configure in Project Settings (workspace.json):

```json
"knowledge_base": {
  "enabled": true,
  "docs_dirs": ["docs"],
  "external_resources": ["https://fastapi.tiangolo.com/"],
  "file_extensions": [".md", ".rst", ".txt"]
}
```

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/services/context_service.py`, `src/agent_pump/models/workspace.py`
- **Tests**: `tests/services/test_context_service_kb.py`, `tests/models/test_workspace_kb.py`

## 🔔 Slack Notifications

Notify users via Slack when workflow events occur.

### Features
- **Workflow Completion**: Sends a success message to Slack when a workflow completes.
- **Workflow Failure**: Sends an error message to Slack when a workflow fails.
- **Configuration**: Simple configuration via workspace settings.

### Configuration
Configure in Workspace Settings:

```json
"notification_config": {
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/...",
    "channel": "#alerts"
  }
}
```

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/services/notification_service.py`, `src/agent_pump/models/notification_config.py`
- **Tests**: `tests/services/test_notification_service.py`, `tests/orchestrator/test_workflow_events.py`

## 🐞 Interactive Troubleshooting

Interactive chat session when a workflow fails to help diagnose and retry issues.

### Features
- **Pause on Error**: Workflows transition to a "troubleshooting" state instead of failing immediately.
- **Error Context**: Automatically captures error logs and stack traces for the failed phase.
- **Chat Interface**: Provides an interactive chat with the agent, pre-loaded with the error context.
- **Retry Mechanism**: Allows users to retry the failed phase directly from the chat interface after applying fixes.

### Usage
1. When a workflow fails, it enters the `Troubleshooting` state.
2. Open the project chat (via `Chat` button or command).
3. The chat will show the error context.
4. Discuss the issue with the agent.
5. Click "Retry Phase" to resume execution from the failed phase.

### Audit Status: ✅ Fully implemented
- **Implementation**: `src/agent_pump/orchestrator/workflow.py`, `src/agent_pump/services/chat_service.py`, `src/agent_pump/tui/screens/chat_screen.py`
- **Tests**: `tests/orchestrator/test_workflow_troubleshooting.py`
