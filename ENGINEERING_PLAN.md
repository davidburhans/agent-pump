# Engineering Plan: Global Backend Configuration

## Objective
Refactor backend configuration to allow defining named backend configurations at the project or global (workspace) level, and referencing them by name in workflow phases. This reduces duplication and enables centralized management of backend settings (models, args, timeouts).

## Current State
- `BackendInstance`: Stores name (type) and args.
- `PhaseBackends`: Stores `BackendFallback` (list of `BackendInstance`) for each phase.
- `ProjectConfig`: Contains `PhaseBackends`.
- `Workspace`: Contains `backend_presets` (named `BackendFallback`s).
- Configuration is largely denormalized; changing a preset in the workspace doesn't update projects unless explicitly re-applied.
- `config.yml` loading in `src/agent_pump/config.py` is simple and doesn't fully expose the `ProjectConfig` capabilities or named definitions.

## Proposed Changes

### 1. Model Updates (`src/agent_pump/models/workspace.py`)
- Update `ProjectConfig` to include:
  - `defined_backends`: `dict[str, BackendInstance]` - Local named backend definitions.
- Update `BackendInstance`:
  - Ensure it's flexible enough to serve as a definition (it already has `name` and `args`). Note: `name` in `BackendInstance` is currently the *backend type* (e.g., "gemini"). We might need to distinguish between "configuration name" (key in dict) and "backend engine name" (value in instance).
  - *Correction*: `BackendInstance.name` is the engine type (gemini/claude). The key in `defined_backends` will be the configuration name.

### 2. Configuration Schema Update (`src/agent_pump/config.py`)
- Update `Config` model (used for `config.yml` parsing) to support:
  - `backends`: `dict[str, BackendConfigDict]` section.
  - `workflow`: Support string values for phases (e.g., `planning: "my-custom-backend"`).

### 3. Logic Refactor (`src/agent_pump/config.py` & `src/agent_pump/services/project_service.py`)
- Implement resolution logic:
  - When loading configuration, if a phase specifies a string name:
    1. Look in `ProjectConfig.defined_backends`.
    2. Look in `Workspace.backend_presets`.
    3. If found, instantiate the backend using the defined config.
    4. If not found, raise validation error or fallback.

### 4. CLI/TUI Updates
- Ensure `config` commands and TUI settings panels expose these new capabilities.
- (Scope limit: Focus on the underlying plumbing and `config.yml` support first. TUI updates can be a follow-up if extensive).

## Implementation Steps

### Step 1: Model Enhancements
- [ ] Modify `ProjectConfig` in `src/agent_pump/models/workspace.py` to add `defined_backends`.
- [ ] Ensure serialization/deserialization works correctly.

### Step 2: Configuration Loader Refactor
- [ ] Update `src/agent_pump/config.py` to parse the new `backends` section in `config.yml`.
- [ ] Implement the resolution logic in `Config.load` (or a post-processing step) to link named backends to phase configurations.

### Step 3: Verification
- [ ] Create a test case with a `config.yml` using named backends.
- [ ] Verify that `ProjectConfig` loads correctly with the resolved backend instances.
- [ ] Verify inheritance from Workspace presets.

## Files to Modify
- `src/agent_pump/models/workspace.py`
- `src/agent_pump/config.py`
- `tests/unit/test_config_creation.py` (or new test file)

## Verification Plan
- Run `uv run pytest tests/unit/test_config_creation.py`
- Create a manual `config.yml` in a temporary project and verify `agent-pump config show` reflects the correct resolved backends.
