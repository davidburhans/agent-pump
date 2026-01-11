# Engineering Plan: Custom Verification Commands

## Goal
Implement support for project-specific build, lint, and test commands via configuration. The system should read commands from `.agent-pump.yml` and auto-detect common patterns (npm, cargo, go, uv, etc.), reporting verification results clearly with an option to skip verification phases.

## Feature Description
Currently, the agent pump has generic verification steps that may not fit all project types. This feature will allow users to define custom verification commands per project through a configuration file. The system should:
1. Read custom commands from `.agent-pump.yml` configuration
2. Auto-detect common project patterns (npm, cargo, go, uv, etc.) to suggest default commands
3. Report verification results clearly to the user
4. Provide an option to skip verification phases when needed

## Implementation Plan

### Phase 1: Configuration Model & Schema
- [ ] Define Pydantic models for verification configuration in `src/agent_pump/models/config.py`
- [ ] Add fields for build_cmd, lint_cmd, test_cmd, and skip_verification flag
- [ ] Create schema validation for command structures
- [ ] Add default detection logic for common project types

### Phase 2: Configuration Loading & Saving
- [ ] Update workspace configuration to include verification settings
- [ ] Implement loading verification config from `.agent-pump.yml`
- [ ] Add methods to save/update verification configuration
- [ ] Create helper functions to detect project type and suggest defaults

### Phase 3: Verification Command Execution
- [ ] Create a verification executor class to run custom commands
- [ ] Implement async execution of build, lint, and test commands
- [ ] Add proper error handling and result reporting
- [ ] Integrate with existing verification phase in the workflow

### Phase 4: TUI Integration
- [ ] Add verification config modal to the TUI
- [ ] Allow editing of build, lint, and test commands
- [ ] Add toggle for skip verification option
- [ ] Display verification results in the UI

### Phase 5: CLI Integration
- [ ] Add CLI commands to manage verification configuration
- [ ] Allow setting commands via command line
- [ ] Add option to skip verification in CLI

### Phase 6: Testing
- [ ] Write unit tests for configuration models
- [ ] Write integration tests for command execution
- [ ] Test auto-detection of project types
- [ ] Test TUI modal functionality

## Task List

- [ ] **Configuration Model Implementation**
    - [ ] Create Pydantic models for verification commands in `src/agent_pump/models/config.py`
    - [ ] Add validation for command structures
    - [ ] Implement project type detection logic

- [ ] **Configuration Management**
    - [ ] Update workspace config to include verification settings
    - [ ] Implement loading from `.agent-pump.yml`
    - [ ] Add saving/updating methods

- [ ] **Verification Executor**
    - [ ] Create verification executor class
    - [ ] Implement async command execution
    - [ ] Add error handling and result reporting

- [ ] **Workflow Integration**
    - [ ] Integrate with existing verification phase
    - [ ] Add skip verification logic
    - [ ] Update state machine if needed

- [ ] **TUI Modal Development**
    - [ ] Create verification config modal
    - [ ] Add form elements for command editing
    - [ ] Implement save/cancel functionality

- [ ] **CLI Commands**
    - [ ] Add verification config CLI commands
    - [ ] Implement command-line configuration options

- [ ] **Testing**
    - [ ] Write unit tests for configuration models
    - [ ] Write integration tests for command execution
    - [ ] Test project type auto-detection
    - [ ] Test TUI modal functionality

- [ ] **Documentation & Examples**
    - [ ] Update README.md with verification command usage
    - [ ] Add examples to documentation

- [ ] **Final Verification**
    - [ ] Test end-to-end functionality
    - [ ] Verify cross-platform compatibility
    - [ ] Check error handling

- [ ] **Reflect on the work done and update BEST_PRACTICES.md with any lessons learned, and check if README.md needs updates as a result**