# Changelog

All notable changes to Agent Pump will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-02-06

### Added
- 🚀 **Initial Production Release** - Agent Pump is ready for production use
- ✨ **Autonomous Workflow Loop** - Plan → Implement → Verify → Brainstorm → Commit cycle
- 🖥️ **Beautiful TUI Dashboard** - Monitor multiple projects with Textual framework
- 🌐 **HTTP API & WebSocket** - Remote monitoring and real-time updates
- 🧠 **Pluggable Backends** - Support for Gemini, Claude Code, OpenCode, and Qwen with fallback chains
- ✅ **Automated Verification** - Runs tests, linters, and builds; auto-fixes failures
- 📝 **Living Roadmap** - Agent reads `ROADMAP.md` to decide what to work on next
- 🌿 **Git Branch Strategy** - Automatic feature branches with optional auto-merge
- 💰 **Cost Tracking** - Monitor API spending with budget limits and alerts
- 🎭 **Dry Run Mode** - Preview changes without modifying files
- 🔄 **Checkpoint Rollback** - Save and restore project states at any point
- 🔐 **API Authentication** - Secure API access with API key middleware

### Backends
- **Gemini** - Full integration with `gemini-cli`
- **Qwen** - Full integration with Qwen API
- **Dry Run** - Preview mode for testing without AI execution

### Testing
- **100+ unit tests** covering core functionality
- **Integration tests** for end-to-end workflows
- **TUI tests** for user interface components
- **Test coverage** for services, models, and orchestrator

### Documentation
- **README.md** - Quick start guide and feature overview
- **docs/features.md** - Complete feature list with configuration examples
- **BEST_PRACTICES.md** - Engineering philosophy and coding standards
- **docs/api.md** - HTTP API and WebSocket documentation
- **docs/verification_commands.md** - Verification commands reference

### CLI Commands
- `agent-pump` - Launch TUI application
- `agent-pump project add <path>` - Add project to workspace
- `agent-pump project list` - List all projects
- `agent-pump project bootstrap <path>` - Initialize project with ROADMAP.md
- `agent-pump ask "<question>" <path>` - Ask questions about codebase
- `agent-pump --web --web-port <port>` - Start web server
- `agent-pump <path> --headless --dry-run` - CI/CD mode
- Budget management: `budget enable/disable/show/config`
- Cost tracking: `cost show/reset/project`
- Checkpoint management: `checkpoint list/restore/delete`

### GitHub Integration
- Pull Request creation with feature linking
- Issue search and linking
- Commit message enhancement with issue references
- Issue closing on completion

### Security
- API key authentication for HTTP/WebSocket endpoints
- Token-based GitHub integration
- No hardcoded credentials
- Secret protection in configuration

### Developer Experience
- Type hints throughout codebase
- Pydantic v2 for data validation
- Async/await patterns
- Rich console output
- Comprehensive error messages

### Platform Support
- **Windows** - Primary development platform
- **Linux** - Supported
- **macOS** - Supported

### Minimum Requirements
- Python 3.12+
- `uv` package manager
- Textual 0.47.0+
- Pydantic 2.5.0+
