# Engineering Plan: Custom Verification Commands

## Feature Description and Goals

Implement support for project-specific build, lint, and test commands via configuration. This feature will allow users to define custom verification commands in a `.agent-pump.yml` configuration file, with auto-detection for common project types (npm, cargo, go, uv, etc.).

## Acceptance Criteria
- Read commands from `.agent-pump.yml`
- Auto-detect common patterns (npm, cargo, go, uv, etc.)
- Report verification results clearly
- Allow skipping verification phases

## Detailed Task List

- [ ] Define Pydantic models for verification configuration (build, lint, test commands with timeouts)
- [ ] Add validation to prevent command injection (block `||`, `&&`, `;`, `$()`, backticks)
- [ ] Extend Project model to include verification configuration
- [ ] Create VerificationExecutor class to handle command execution with timeouts
- [ ] Implement auto-detection logic for common project types (package.json, Cargo.toml, go.mod, pyproject.toml, etc.)
- [ ] Add configuration options to TUI modal for verification commands
- [ ] Integrate verification commands into the workflow after AI verification succeeds
- [ ] Implement sequential execution (build → lint → test) with early failure
- [ ] Add visual indicators to project cards showing verification configuration status
- [ ] Update workspace configuration to support verification commands
- [ ] Add CLI options to configure verification commands
- [ ] Create unit tests for verification configuration models
- [ ] Create unit tests for verification executor
- [ ] Create integration tests for workflow integration
- [ ] Document the new configuration options in README.md
- [ ] Reflect on the work done and update BEST_PRACTICES.md with any lessons learned, and check if README.md needs updates as a result