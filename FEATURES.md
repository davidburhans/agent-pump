
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
