# Configuration Reference Guide

Complete reference for all Agent Pump configuration options.

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration Locations](#configuration-locations)
- [Backend Configuration](#backend-configuration)
- [Workflow Configuration](#workflow-configuration)
- [Budget & Cost Tracking](#budget--cost-tracking)
- [Checkpoint Configuration](#checkpoint-configuration)
- [GitHub Integration](#github-integration)
- [API Server Configuration](#api-server-configuration)
- [Environment Variables](#environment-variables)

## Quick Start

### Minimal Configuration

For quick start, you only need a `ROADMAP.md` in your project:

```markdown
## Current Sprint

### 🔴 Add Login Page
Create a login page with email and password fields.
```

Then run Agent Pump:

```bash
uv run agent-pump
# Press 'a' to add your project
# Press 's' to start workflow
```

## Configuration Locations

Agent Pump looks for configuration files in the following order:

1. **Project-level**: `.agent-pump/config.yml` (gitignored, not committed)
2. **User-level**: `~/.config/agent-pump/config.yml` (global defaults)
3. **Environment Variables**: Override any file-based config

Example `~/.config/agent-pump/config.yml`:

```yaml
# Global default configuration
backends:
  default: gemini

# GitHub integration (optional)
github:
  token: ghp_xxxxxxxxxxxxxx  # Or use GITHUB_TOKEN env var
  owner: yourusername
  repo: your-repo
  base_branch: main

# Cost tracking (optional)
budget:
  enabled: true
  weekly_limit: 100.00
  monthly_limit: 400.00
  action_on_exceeded: warn

# Workflow configuration
workflow:
  phases: plan,implement,verify,brainstorm,commit
  auto_continue: true
  max_iterations: 10

# Verification commands
verification:
  test_command: uv run pytest
  lint_command: uv run ruff check .
  build_command: uv run pyright
```

## Backend Configuration

### Backend Selection

```yaml
backends:
  default: gemini  # Primary backend
  fallback_chain:
    - qwen
    - claude
    - opencode
```

### Backend-Specific Settings

#### Gemini

```yaml
backends:
  gemini:
    model: gemini-2.5-pro  # gemini-2.5-flash, gemini-1.5-pro, etc.
    temperature: 0.7
    max_retries: 3
```

#### Qwen

```yaml
backends:
  qwen:
    model: qwen-turbo  # qwen-plus, qwen-max, etc.
    temperature: 0.7
    max_retries: 3
```

#### Claude Code

```yaml
backends:
  claude:
    model: claude-3-5-sonnet-20241022
    temperature: 0.7
    max_retries: 3
```

#### OpenCode

```yaml
backends:
  opencode:
    model: gpt-4  # or other available models
    temperature: 0.7
    max_retries: 3
```

See [backend_setup.md](backend_setup.md) for detailed setup instructions.

## Workflow Configuration

### Phase Order

Default phase sequence: `plan → implement → verify → brainstorm → commit`

```yaml
workflow:
  phases:
    - plan
    - implement
    - verify
    - brainstorm
    - commit
```

### Custom Workflows

```yaml
workflow:
  custom:
    my_workflow:
      phases:
        - analyze
        - design
        - implement
        - test
      max_iterations: 5
      auto_continue: false
```

### Phase Behavior

| Phase | Description |
|--------|-------------|
| plan | Analyze codebase and create implementation plan |
| implement | Write code according to plan |
| verify | Run tests, linters, and builds |
| brainstorm | Review work and suggest improvements |
| commit | Stage and commit changes to git |

### Auto-Continue

```yaml
workflow:
  auto_continue: true  # Keep running until feature complete
  max_iterations: 10  # Max cycles before stopping
```

### Headless Mode

For CI/CD:

```bash
uv run agent-pump ./your-project --headless --dry-run
```

## Budget & Cost Tracking

### Enable Budget Enforcement

```yaml
budget:
  enabled: true
  weekly_limit: 100.00  # USD
  monthly_limit: 400.00  # USD
  action_on_exceeded: warn  # or stop, notify
```

### Action on Exceeded

- `warn`: Show warning but continue
- `stop`: Stop workflow immediately
- `notify`: Send notification only

### Cost Commands

```bash
# Show costs for current project
uv run agent-pump cost show ./your-project

# Show budget status
uv run agent-pump budget show

# Reset costs for project
uv run agent-pump cost reset ./your-project

# Configure budget limits
uv run agent-pump budget enable
uv run agent-pump budget disable
uv run agent-pump budget config --weekly 50 --monthly 200 --action stop
```

## Checkpoint Configuration

### Maximum Checkpoints

```yaml
checkpoint:
  max_checkpoints: 50  # Default, trim older entries
```

### Auto-Checkpoints

Created before each workflow phase by default. Can be disabled:

```yaml
checkpoint:
  auto_create: false  # Disable automatic checkpointing
```

### Manual Checkpoints

In TUI, press `c` to create manual checkpoint.

### Commands

```bash
# List checkpoints
uv run agent-pump checkpoint list ./your-project

# Restore from checkpoint
uv run agent-pump checkpoint restore <checkpoint-id> ./your-project

# Delete checkpoint
uv run agent-pump checkpoint delete <checkpoint-id> ./your-project
```

## GitHub Integration

### Enable GitHub Features

```yaml
github:
  token: ghp_xxxxxxxxxxxxxx  # Or GITHUB_TOKEN environment variable
  owner: yourusername
  repo: your-repo-name
  base_branch: main  # Target branch for pull requests
  auto_merge: true  # Auto-merge PRs
```

### Pull Request Behavior

```yaml
github:
  pr:
    title_prefix: "feat:"  # Conventional commits
    body_template: "Auto-generated by Agent Pump"
    assign_reviewers: false  # Don't auto-assign
```

### Issue Integration

Agent Pump can:

- Search for existing issues
- Link commits to issues (#123)
- Close issues on completion

```yaml
github:
  issue:
    search_enabled: true
    link_commits: true  # Add #123 to commit messages
    close_on_complete: true
```

## API Server Configuration

### Start Web Server

```bash
# Basic HTTP server
uv run agent-pump --web --web-port 8080

# With API key authentication
uv run agent-pump --web --web-port 8080 --api-key your-secret-key

# Custom host
uv run agent-pump --web --web-host 0.0.0.0 --web-port 8080
```

### Environment Variables

```bash
# API key (required for auth)
export AGENT_PUMP_API_KEY="your-secret-key"

# Disable desktop notifications (useful in CI)
export AGENT_PUMP_NO_NOTIFY=1

# Debug logging
export AGENT_PUMP_DEBUG=1

# Custom config location
export AGENT_PUMP_CONFIG_DIR="/custom/path"
```

### WebSocket Configuration

```yaml
api:
  websocket:
    enabled: true
    ping_interval: 30  # Seconds between heartbeats
    max_connections: 100
```

## Environment Variables

### API Keys

| Variable | Backend | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Gemini | Google API key |
| `ANTHROPIC_API_KEY` | Claude | Anthropic API key |
| `DASHSCOPE_API_KEY` | Qwen | Alibaba Cloud API key |
| `OPENCODE_API_KEY` | OpenCode | OpenCode.ai API key |

### GitHub

| Variable | Description |
|----------|-------------|
| `GITHUB_TOKEN` | GitHub personal access token |

### General

| Variable | Description |
|----------|-------------|
| `AGENT_PUMP_CONFIG_DIR` | Custom config directory path |
| `AGENT_PUMP_DEBUG` | Enable debug logging (1) |
| `AGENT_PUMP_NO_NOTIFY` | Disable desktop notifications (1) |
| `AGENT_PUMP_API_KEY` | API authentication key for web server |

### Agent-Specific Override

Override backend-specific model settings via environment variables:

```bash
# For Gemini
export AGENT_PUMP_GEMINI_MODEL=gemini-2.5-pro

# For Qwen
export AGENT_PUMP_QWEN_MODEL=qwen-turbo

# For Claude
export AGENT_PUMP_CLAUDE_MODEL=claude-3-5-sonnet
```

## Best Practices

1. **Use Environment Variables for Secrets**
   - Never commit API keys
   - Use `.env` files locally
   - Reference in `.agent-pump/config.yml`

2. **Test in Dry-Run First**
   - Use `--dry-run` flag
   - Verify workflow before enabling auto-execution

3. **Start Simple**
   - Use Gemini backend (most stable)
   - Test with single feature first
   - Enable additional backends after basic workflow works

4. **Configure Budgets**
   - Set weekly/monthly limits early
   - Monitor costs in first few workflows
   - Adjust based on actual usage

5. **Use Checkpoints**
   - Create checkpoints before risky changes
   - Test rollback functionality
   - Regular checkpoint cleanup

## Complete Example

```yaml
# ~/.config/agent-pump/config.yml

# Backend selection
backends:
  default: gemini
  gemini:
    model: gemini-2.5-pro
    temperature: 0.7
  fallback_chain:
    - qwen
      model: qwen-turbo
    - claude
      model: claude-3-5-sonnet-20241022

# GitHub integration
github:
  token: ${GITHUB_TOKEN}  # Reads from environment
  owner: ${GITHUB_USER}
  repo: ${GITHUB_REPO}
  base_branch: main
  auto_merge: false
  pr:
    title_prefix: "feat:"

# Cost tracking
budget:
  enabled: true
  weekly_limit: 100.00
  monthly_limit: 400.00
  action_on_exceeded: warn

# Workflow settings
workflow:
  auto_continue: true
  max_iterations: 10
  phases:
    - plan
    - implement
    - verify
    - brainstorm
    - commit

# Verification
verification:
  test_command: uv run pytest
  lint_command: uv run ruff check .
  build_command: uv run pyright

# Checkpoints
checkpoint:
  max_checkpoints: 50
  auto_create: true

# API server
api:
  enabled: false
  port: 8080
  api_key: ${AGENT_PUMP_API_KEY}  # Optional
```

## Next Steps

1. Configure your backend in `~/.config/agent-pump/config.yml`
2. Set up API keys as environment variables
3. Create a project with `ROADMAP.md`
4. Test with `--dry-run` flag first
5. Run your first workflow!

For more information:
- [README.md](../README.md)
- [features.md](features.md)
- [backend_setup.md](backend_setup.md)
- [API Documentation](docs/api.md)
